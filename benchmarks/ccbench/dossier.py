"""Case dossier generator. Reads a finished bench run, writes one folder per case so a reviewer can open the evidence.

  python dossier.py <bench> --run DIR --out DIR [--data DIR] [--native DIR] [--meta KEY=VALUE ...]

Benches: admission, gatebench, trapcheck, planner, nativeadmit, planbench. It never runs a model, docker or a harness and never
writes into --run. Stdlib only.

Layout of every case folder (the same for every bench):
  input/     exactly what each arm was given (input/ARMS.md says which file went to which arm)
  ours/      the Capability Capsule arm's raw outputs, records and stop reasons, as produced
  theirs/    the opponent arm's raw outputs, as produced (theirs/MISSING.md when the run has none)
  oracle/    the gold answer and HOW.md (how it was made, why it is independent of both arms)
  score.json per-arm verdict, the rule that produced it (file:function) and the class
  run.json   command, commit, image, model, timestamps, tokens, wall time (from RUN/run-meta/*.json written by scripts/ai4r-bench;
             "not recorded" when the source lacks it)
  case.md    one page: what was asked, what we did, what they did, gold, verdict
Per bench: INDEX.md (cases with both classes), claims.json (headline numbers recomputed from the case scores) and
GAPS.md (what a skeptic could ask that this data cannot answer).
Files copied from the run are byte-identical to the source. Files this script writes use LF endings.
"""
import argparse
import hashlib
from datetime import datetime
import importlib.util
import json
import random
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import roots  # noqa: E402

NR = 'not recorded'
NA_MODEL = 'none (deterministic offline computation, no model call)'
LIMIT = 1 << 20          # files above this are listed with sha256 and source path instead of copied
BENCHES = ('admission', 'gatebench', 'trapcheck', 'planner', 'nativeadmit', 'planbench')
CLASSES = ('correct_delivered', 'wrong_delivered', 'correct_stop', 'wrong_stop', 'false_reject')


# ---------------------------------------------------------------- files

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes().decode('utf-8-sig'))


def load_lines(path):
    text = Path(path).read_bytes().decode('utf-8-sig')
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def to_bytes(data):
    if isinstance(data, bytes):
        return data
    return data.replace('\r\n', '\n').encode('utf-8')


def jtext(value):
    return json.dumps(value, indent=1, ensure_ascii=False, default=str) + '\n'


def put(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(to_bytes(data))


def put_json(path, value):
    put(path, jtext(value))


def table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|']
    for row in rows:
        lines.append('| ' + ' | '.join(str(c).replace('|', '/').replace('\n', ' ') for c in row) + ' |')
    return '\n'.join(lines) + '\n'


def first_existing(*paths):
    for p in paths:
        if p and Path(p).exists():
            return Path(p)
    return None


class Part:
    """One folder of a case (input, ours, theirs, oracle). Large files become entries in NOT-COPIED.json."""

    def __init__(self, root):
        self.root = Path(root)
        self.refs = []
        self.absent = []

    def put(self, name, data):
        put(self.root / name, data)

    def json(self, name, value):
        put_json(self.root / name, value)

    def copy(self, src, name=None):
        """Copy src byte for byte (or list it when over LIMIT). Returns True when src exists."""
        src = Path(src)
        name = name or src.name
        if not src.is_file():
            self.absent.append({'name': name, 'source': str(src)})
            return False
        size = src.stat().st_size
        if size > LIMIT:
            self.refs.append({'name': name, 'bytes': size, 'sha256': sha256_file(src), 'source': str(src)})
            return True
        dst = self.root / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return True

    def ref(self, name, src):
        src = Path(src)
        self.refs.append({'name': name, 'bytes': src.stat().st_size, 'sha256': sha256_file(src), 'source': str(src)})

    def close(self):
        if self.refs:
            put_json(self.root / 'NOT-COPIED.json', {'why': 'over %d bytes; sha256 and source path listed instead' % LIMIT,
                                                      'files': self.refs})
        if self.absent:
            put_json(self.root / 'NOT-FOUND.json', {'why': 'expected in the run or source tree but absent', 'files': self.absent})


class Case:
    def __init__(self, bench_out, name):
        self.name = name
        self.dir = Path(bench_out) / name
        self.input = Part(self.dir / 'input')
        self.ours = Part(self.dir / 'ours')
        self.theirs = Part(self.dir / 'theirs')
        self.oracle = Part(self.dir / 'oracle')

    def files(self, sub):
        base = self.dir / sub
        if not base.is_dir():
            return []
        return sorted(p.relative_to(self.dir).as_posix() for p in base.rglob('*') if p.is_file())

    def links(self, subs, cap=40):
        found = [f for s in subs for f in self.files(s)]
        lines = ['- [%s](%s)' % (f, f) for f in found[:cap]]
        if len(found) > cap:
            lines.append('- ... %d more files in %s' % (len(found) - cap, ', '.join(subs)))
        return '\n'.join(lines) + ('\n' if lines else '')

    def finish(self, title, asked, we, they, gold, verdict, score, run):
        for part in (self.input, self.ours, self.theirs, self.oracle):
            part.close()
        score = dict(case=self.name, **score)
        put_json(self.dir / 'score.json', score)
        put_json(self.dir / 'run.json', run)
        text = ['# ' + title, '']
        for heading, body, subs in (('what was asked', asked, ['input']), ('what we did', we, ['ours']),
                                    ('what they did', they, ['theirs']), ('gold', gold, ['oracle']),
                                    ('verdict', verdict, ['score.json', 'run.json'])):
            text += ['## ' + heading, '', body.strip(), '']
            if heading == 'verdict':
                text += ['- [score.json](score.json)', '- [run.json](run.json)', '']
            else:
                text += [self.links(subs).rstrip(), '']
        put(self.dir / 'case.md', '\n'.join(text))


META = []     # run-meta records of the run being read (scripts/ai4r-bench writes them), set by main()


def load_meta(run):
    found = []
    for path in sorted((Path(run) / 'run-meta').glob('*.json')):
        try:
            found.append(dict(load(path), run_meta_file=path.name))
        except ValueError:
            pass
    return found


def meta_fields(metas):
    """What run-meta can say about a run: command, commit, image, start, end, wall time. Empty when there is none."""
    if not metas:
        return {}
    commits = []
    for m in metas:
        prod = m.get('product') or {}
        label = (prod.get('commit') or 'unknown') + (' (working tree dirty)' if prod.get('dirty') else '')
        if label not in commits:
            commits.append(label)
    starts = sorted(m['started_at'] for m in metas if m.get('started_at'))
    ends = sorted(m['finished_at'] for m in metas if m.get('finished_at'))
    images = []
    for m in metas:
        img = m.get('image')
        if img and (img.get('tag'), img.get('id')) not in images:
            images.append((img.get('tag'), img.get('id')))
    fields = dict(command=[' '.join(['ai4r-bench'] + m.get('ai4r_bench_args', [])) for m in metas],
                  product_commit=commits[0] if len(commits) == 1 else commits,
                  image=('host Python (no container)' if not images else images[0][0] + ' ' + str(images[0][1]) if len(images) == 1 else [list(i) for i in images]),
                  started_at=starts[0] if starts else NR, finished_at=ends[-1] if ends and len(ends) == len(metas) else NR,
                  exit_codes=[m.get('exit_code') for m in metas], run_meta=metas)
    if starts and ends and len(ends) == len(metas):
        t0, t1 = [datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ') for x in (starts[0], ends[-1])]
        fields['wall_time_s'] = (t1 - t0).total_seconds()
    codex = [m['codex'] for m in metas if m.get('codex')]
    if codex:
        fields['codex'] = codex[0]
    return fields


def run_record(use_meta=True, **known):
    base = dict(command=NR, product_commit=NR, image=NR, model=NR, started_at=NR, finished_at=NR, tokens=NR, wall_time_s=NR)
    if use_meta:
        base.update(meta_fields(META))
    for key, value in known.items():
        if value is not None and not (value == NR and base.get(key, NR) != NR):    # run-meta fills what a bench does not know
            base[key] = value
    return base


def ran_gap(default, recorded):
    """The 'how exactly it was run' gap: the old text without run-meta, the recorded one with it."""
    if not META:
        return default
    commits = sorted({(m.get('product') or {}).get('commit') or 'unknown' for m in META})
    dirty = any((m.get('product') or {}).get('dirty') for m in META)
    return recorded + ' Run-meta (run.json): argv, mode, image id, product commit %s%s, start, end and exit code.' % (
        ', '.join(c[:12] for c in commits), ' with a dirty working tree (tracked changes beyond that commit are summarized by diff_head_sha256 only; the diff itself is not stored)' if dirty else '')


def arm_score(arm, verdict, cls, rule, **extra):
    return dict(arm=arm, verdict=verdict, **{'class': cls}, rule=rule, **extra)


def count_classes(items):
    counts = {}
    for c in items:
        counts[c] = counts.get(c, 0) + 1
    return dict(sorted(counts.items()))


def fmt_counts(counts):
    return ', '.join('%s %s' % (k, v) for k, v in counts.items()) or '-'


def one_class(counts):
    return next(iter(counts)) if len(counts) == 1 else 'mixed'


# ---------------------------------------------------------------- claims and index

def same_value(a, b):
    if a is None or b is None:
        return a is b
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return a == b
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def claim(cid, text, headline, recomputed, source, numerator=None, denominator=None, note=''):
    """headline: the harness's own number (None when the run has no such number to compare)."""
    if headline is NR or headline is None and note.startswith('no headline'):
        status = 'no-headline'
    else:
        status = 'match' if same_value(headline, recomputed) else 'MISMATCH'
    return {'id': cid, 'claim': text, 'headline': headline, 'recomputed': recomputed, 'status': status,
            'headline_source': source, 'numerator': numerator or {}, 'denominator': denominator or {}, 'note': note}


def finish_bench(out, bench, cases, claims, gaps, intro, columns=('ours', 'theirs')):
    out = Path(out)
    bad = [c for c in claims if c['status'] == 'MISMATCH']
    put_json(out / 'claims.json', {'bench': bench, 'all_match': not bad, 'mismatches': [c['id'] for c in bad],
                                    'checked': len([c for c in claims if c['status'] != 'no-headline']), 'claims': claims})
    lines = ['# Dossier index: ' + bench, '']
    if bad:
        lines += ['**CLAIM MISMATCH: %d headline number(s) do not equal the recomputation from the case scores: %s. See claims.json.**'
                  % (len(bad), ', '.join(c['id'] for c in bad)), '']
        print('*** CLAIM MISMATCH in %s: %s' % (bench, ', '.join('%s (headline %s, recomputed %s)' % (c['id'], c['headline'], c['recomputed']) for c in bad)),
              file=sys.stderr)
    lines += [intro.strip(), '',
              'Folder layout: input/ (what each arm was given, ARMS.md), ours/, theirs/, oracle/ (gold + HOW.md), score.json, run.json, case.md.',
              'Bench files: [claims.json](claims.json) (headline numbers recomputed), [GAPS.md](GAPS.md) (what this data cannot answer).', '',
              '## Cases (%d)' % len(cases), '']
    lines.append(table(['case'] + list(columns), [['[%s](%s/case.md)' % (c['folder'], c['folder']), c['ours'], c['theirs']] for c in cases]).rstrip())
    lines += ['', '## Headline numbers', '']
    rows = [[c['id'], c['claim'], c['headline'], c['recomputed'], c['status']] for c in claims]
    lines.append(table(['id', 'claim', 'harness headline', 'recomputed', 'status'], rows).rstrip())
    put(out / 'INDEX.md', '\n'.join(lines) + '\n')
    put(out / 'GAPS.md', '# What this data cannot answer (%s)\n\n%s\n' % (bench, '\n'.join('- ' + g for g in gaps)))
    return len(cases), len(claims), len(bad)


def not_recorded_note(*names):
    return ', '.join(names)


# ---------------------------------------------------------------- admission

ADM = HERE / 'admission'
ADM_RULE = {
    'CC': 'benchmarks/ccbench/admission/study.py:run (CC admitted iff every derived test passes; study.py:assess, oracle.py:matches)',
    'CC_THIN': 'benchmarks/ccbench/admission/study.py:run (thin declaration: typed ports only, output types checked; study.py:thin)',
    'SKILL': 'benchmarks/ccbench/admission/study.py:run (SKILL admits unless a wrong result is observed in up to 20 uses; oracle.py:matches)',
}


def adm_input(run, name):
    return first_existing(Path(run) / name, ADM / name)


def admit_class(defective, admitted):
    if defective:
        return 'wrong_delivered' if admitted else 'correct_stop'
    return 'correct_delivered' if admitted else 'false_reject'


def build_admission(run, out, args):
    R = Path(run)
    results = load(R / 'results.json')
    labels = load(adm_input(R, 'ground_truth.json'))
    decls = load(adm_input(R, 'declarations.json'))
    routes = [r for r in ('CC', 'CC_THIN', 'SKILL') if (R / (r.lower() + '_trials.json')).exists() and r in results]
    trials = {r: load(R / (r.lower() + '_trials.json')) for r in routes}
    by = {r: {} for r in routes}
    for r in routes:
        for row in trials[r]:
            by[r].setdefault(row['candidate'], []).append(row)
        for rows in by[r].values():
            rows.sort(key=lambda x: x['repeat'])
    derived = load(R / 'derived_tests.json') if (R / 'derived_tests.json').exists() else None
    evidence = load(R / 'admission_evidence.json') if (R / 'admission_evidence.json').exists() else None
    streams_path = R / 'usage_streams.json'
    streams = {(s['tool'], s['repeat']): s for s in load(streams_path)} if streams_path.exists() else {}
    frozen = load(R / 'frozen_manifest.json') if (R / 'frozen_manifest.json').exists() else None
    skills_md = adm_input(R, 'SKILLS.md')
    reps = len({row['repeat'] for row in trials['CC']}) if 'CC' in trials else len({row['repeat'] for row in trials[routes[0]]})
    cases = []
    gaps = []
    for label in labels:
        name, tool = label['candidate'], label['tool']
        if not all(name in by[r] for r in routes):
            continue
        case = Case(out, name)
        cand = first_existing(R / 'candidates' / (name + '.py'), ADM / 'candidates' / (name + '.py'))
        if cand:
            case.input.copy(cand, 'candidate_tool.py')
        else:
            case.input.absent.append({'name': 'candidate_tool.py', 'source': name})
        case.input.json('declaration_rich.json', decls[tool])
        if derived:
            case.input.json('derived_tests_CC.json', derived['CC'][tool])
            if 'CC_THIN' in derived:
                case.input.json('derived_tests_CC_THIN.json', derived['CC_THIN'][tool])
        if skills_md:
            case.input.copy(skills_md, 'SKILLS.md')
        sk = by.get('SKILL', {}).get(name, [])
        detected = [r['repeat'] for r in sk if r['first_failure_use'] is not None]
        silent = [r['repeat'] for r in sk if r['first_failure_use'] is None]
        examples = []
        for rep in (detected[:1] + silent[:1]) or [by[routes[0]][name][0]['repeat']]:
            examples.append(rep)
            if (tool, rep) in streams:
                case.input.json('usage_stream_rep%02d.json' % rep, streams[(tool, rep)])
        if streams_path.exists():
            case.input.ref('usage_streams.json (all %d reps, all tools)' % reps, streams_path)
        case.input.put('ARMS.md', '\n'.join([
            '# What each arm was given', '',
            '- No model was involved. Prompt actually sent: none (deterministic offline study, see admission/README.md).',
            '- Both arms are judged on the same candidate tool: candidate_tool.py.',
            '- ours (CC): the rich declaration (declaration_rich.json) and the tests derived from it by admission/derive.py (derived_tests_CC.json). It reads no candidate source and no defect label.',
            '- ours (CC_THIN, sensitivity): typed ports only (derived_tests_CC_THIN.json).',
            '- theirs (SKILL): only the prose in SKILLS.md and a stream of 20 synthetic uses per repetition (usage_stream_rep*.json shows the example reps; the full file is listed in NOT-COPIED.json).', '']))
        # ours
        counts_by_route = {}
        for r in routes:
            counts_by_route[r] = count_classes(admit_class(label['defective'], row['admitted']) for row in by[r][name])
        if evidence and 'CC' in evidence and name in evidence['CC']:
            ev = evidence['CC'][name]
            case.ours.json('cc_admission_evidence.json', ev)
            failed = [e for e in ev['evidence'] if not e['pass']]
            case.ours.json('cc_stop_reason.json', {
                'admitted': ev['admitted'], 'tests_run': ev['tests_run'], 'failed_tests': ev['failed_tests'],
                'first_failed_test': failed[0] if failed else None,
                'meaning': 'CC admits iff every derived test passes; the first failing test is the stop reason' if failed else 'all derived tests passed'})
            if 'CC_THIN' in evidence and name in evidence['CC_THIN']:
                case.ours.json('cc_thin_admission_evidence.json', evidence['CC_THIN'][name])
        for r in routes:
            if r == 'SKILL':
                continue
            rows = by[r][name]
            case.ours.json('%s_reps.json' % r.lower(), [{k: v for k, v in row.items() if k != 'history'} for row in rows])
            for rep in examples:
                case.ours.json('%s_example_rep%02d.json' % (r.lower(), rep), next(x for x in rows if x['repeat'] == rep))
        case.ours.put('reps.md', '# CC admission per repetition\n\n' + rep_table(by['CC'][name]) if 'CC' in by else 'no CC trials')
        # theirs
        if sk:
            case.theirs.json('skill_reps.json', [{k: v for k, v in row.items() if k != 'history'} for row in sk])
            case.theirs.put('reps.md', '# SKILL probation per repetition\n\n' + rep_table(sk))
            for rep in examples:
                case.theirs.json('skill_example_rep%02d.json' % rep, next(x for x in sk if x['repeat'] == rep))
        # oracle
        case.oracle.json('ground_truth.json', label)
        case.oracle.put('HOW.md', '\n'.join([
            '# How the gold was made', '',
            '- Label and witness (`ground_truth.json`): handwritten counterexample and expected outcome for each planted defect; the reference candidate has none.',
            '  Source: benchmarks/ccbench/admission/ground_truth.json (the run folder holds a copy when it was written by the harness).',
            '- Per-use correctness (the `correct` field in every history entry) comes from `admission/oracle.py:matches`, an independent executor of the declared semantics',
            '  (Fraction arithmetic and integer half-even rounding, no import of the candidates, declarations or the test generator).',
            '- Independence from both arms: the ground truth is consulted for labels and validation only, never to generate tests, sample uses or decide admission (admission/README.md).',
            '- Not independent of the author: the same author wrote the declarations, the defects and the usage sampler; no blind second authorship is claimed (admission/README.md).', '']))
        score = {'defective': label['defective'], 'defect': label['defect'], 'reps': len(by[routes[0]][name]),
                 'ours': arm_score('CC', 'admitted' if by['CC'][name][0]['admitted'] else 'rejected', one_class(counts_by_route['CC']), ADM_RULE['CC'],
                                   class_counts=counts_by_route['CC'])}
        if 'CC_THIN' in routes:
            score['ours_thin'] = arm_score('CC_THIN', 'admitted' if by['CC_THIN'][name][0]['admitted'] else 'rejected',
                                           one_class(counts_by_route['CC_THIN']), ADM_RULE['CC_THIN'], class_counts=counts_by_route['CC_THIN'])
        if sk:
            score['theirs'] = arm_score('SKILL', '%d of %d reps admitted' % (sum(r['admitted'] for r in sk), len(sk)), one_class(counts_by_route['SKILL']),
                                        ADM_RULE['SKILL'], class_counts=counts_by_route['SKILL'],
                                        failures_delivered_before_stop=sum(r['failures_delivered_through_detection'] for r in sk))
        mean_detect = [r['first_failure_use'] for r in sk if r['first_failure_use'] is not None]
        run_json = run_record(command=NR, model=NA_MODEL, tokens='not applicable (no model call)',
                              seed=(frozen or {}).get('seed', NR), uses_per_probation=(frozen or {}).get('N', NR),
                              repetitions=(frozen or {}).get('repetitions', reps), frozen_manifest=('frozen_manifest.json in the run' if frozen else NR),
                              candidate_sha256=((frozen or {}).get('files', {}).get('candidates/%s.py' % name, NR)))
        asked = ('Decide whether the tool `%s` (%s) may be admitted for use. Defect planted: %s. Defective: %s. No prompt exists; the arms are deterministic code.'
                 % (name, tool, label['defect'], label['defective']))
        ev_cc = evidence['CC'][name] if evidence and name in evidence.get('CC', {}) else None
        we = ('CC: %s derived tests from the rich declaration. Admitted: %s (%s failed).%s' % (
            ev_cc['tests_run'] if ev_cc else '?', by['CC'][name][0]['admitted'], ev_cc['failed_tests'] if ev_cc else '?',
            ' CC_THIN admitted: %s.' % by['CC_THIN'][name][0]['admitted'] if 'CC_THIN' in by else ''))
        they = ('SKILL: up to 20 observed uses per repetition, stop at the first wrong result. Over %d reps: detected %d, admitted %d. Mean first failure use (detected only): %s.'
                % (len(sk), len(detected), sum(r['admitted'] for r in sk), '%.2f' % (sum(mean_detect) / len(mean_detect)) if mean_detect else 'none'))
        verdict = 'CC class: %s. SKILL classes over reps: %s.' % (fmt_counts(counts_by_route['CC']), fmt_counts(counts_by_route.get('SKILL', {})))
        case.finish('%s (%s)' % (name, 'defective: ' + label['defect'] if label['defective'] else 'correct control'), asked, we, they,
                    'Defect label and witness: see oracle/ground_truth.json. How the gold was made: oracle/HOW.md.', verdict, score, run_json)
        cases.append({'folder': name, 'ours': 'CC %s; thin %s' % (fmt_counts(counts_by_route['CC']), fmt_counts(counts_by_route.get('CC_THIN', {}))),
                      'theirs': 'SKILL ' + fmt_counts(counts_by_route.get('SKILL', {}))})
    claims = adm_claims(results, trials, routes, reps, labels, by)
    gaps = [
        'Input: the SKILL arm is a simulated policy, not a model or a real skill. Its "outputs" are the candidate tool run on synthetic uses; there is no opponent transcript because there is no opponent agent.',
        'Gold provenance: ground_truth.json and oracle.py were written by the same author as the candidates, declarations and usage sampler. No blind second author, no preregistration (admission/README.md).',
        'Usage distribution: usage.py is an assumed office-data distribution, not production telemetry. Only the example reps carry their full 20-use stream in each folder; the other reps are in usage_streams.json (listed by sha256).',
        ran_gap('How exactly it was run: the run folder does not store the command line, product commit, container image or digest, start or end time, or wall time. run.json says "not recorded" for each. Only seed, N and repetitions are in frozen_manifest.json.',
                'How exactly it was run: seed, N and repetitions are in frozen_manifest.json.'),
        'Tokens: not applicable (no model). A reviewer asking for model cost gets nothing because there was no model.',
        'The thin declaration used for CC_THIN is not stored; it is rebuilt from the rich one by study.py:thin. Only its derived tests (derived_tests_CC_THIN.json) are in the run.',
        'failures_strictly_before_detection is 0 by construction under the immediate oracle (README), so that column cannot show a lag.',
        'Gold independence from the candidates rests on oracle.py not importing them; shared primitives (Python csv parser) are a stated common-mode risk.']
    if evidence is None:
        gaps.append('admission_evidence.json was absent: cc_admission_evidence.json and the stop reasons could not be written.')
    if not streams:
        gaps.append('usage_streams.json was absent: the inputs of the SKILL uses are only visible inside the history entries.')
    intro = ('Admission study: tool candidates (14 planted defects, 2 correct controls). ours = CC (declaration-derived tests before use; CC_THIN is the thin-declaration sensitivity); '
             'theirs = SKILL (observe up to 20 uses). One folder per candidate, 100-rep summaries in reps.md, two example reps in full.')
    n = finish_bench(out, 'admission', cases, claims, gaps, intro, ('ours (CC; CC_THIN)', 'theirs (SKILL, classes over reps)'))
    return n


def rep_table(rows):
    return table(['rep', 'admitted', 'pre_admitted', 'first_failure_use', 'right_censored', 'restricted_lag_20', 'failures_delivered'],
                 [[r['repeat'], r['admitted'], r['pre_admitted'], r['first_failure_use'], r['right_censored'], r['restricted_lag_20'],
                   r['failures_delivered_through_detection']] for r in rows])


def adm_claims(results, trials, routes, reps, labels, by):
    claims = []
    defective = {l['candidate'] for l in labels if l['defective']}
    correct = {l['candidate'] for l in labels if not l['defective']}
    ndef = len(defective & set(by[routes[0]]))
    ncor = len(correct & set(by[routes[0]]))
    specs = [
        ('defects_admitted', 'defective candidates admitted per repetition (of %d)' % ndef, lambda r: r['defective'] and r['admitted'], defective),
        ('defects_rejected', 'defective candidates rejected per repetition (of %d)' % ndef, lambda r: r['defective'] and not r['admitted'], defective),
        ('false_rejections', 'correct candidates rejected per repetition (of %d)' % ncor, lambda r: (not r['defective']) and not r['admitted'], correct),
    ]
    for route in routes:
        rows = trials[route]
        for key, text, pred, scope in specs:
            by_case = {}
            for r in rows:
                if pred(r):
                    by_case[r['candidate']] = by_case.get(r['candidate'], 0) + 1
            total = sum(by_case.values())
            claims.append(claim('%s.%s' % (route, key), '%s: %s' % (route, text), results[route][key]['mean'], total / reps,
                                'results.json %s.%s.mean' % (route, key), {'total candidate-reps': total, 'by_case': by_case},
                                {'repetitions': reps, 'cases': sorted(scope & set(by[route]))}))
        fd = {}
        for r in rows:
            if r['failures_delivered_through_detection']:
                fd[r['candidate']] = fd.get(r['candidate'], 0) + r['failures_delivered_through_detection']
        claims.append(claim('%s.failures_delivered_through_detection' % route, '%s: consumer failures delivered per repetition' % route,
                            results[route]['failures_delivered_through_detection']['mean'], sum(fd.values()) / reps,
                            'results.json %s.failures_delivered_through_detection.mean' % route, {'total': sum(fd.values()), 'by_case': fd}, {'repetitions': reps}))
        lag = {}
        for r in rows:
            if r['defective']:
                lag[r['candidate']] = lag.get(r['candidate'], 0) + r['restricted_lag_20']
        claims.append(claim('%s.restricted_lag_20' % route, '%s: mean restricted lag (uses) over defective candidates' % route,
                            results[route]['restricted_lag_20']['mean'], sum(lag.values()) / (reps * ndef) if ndef else None,
                            'results.json %s.restricted_lag_20.mean' % route, {'sum of lags': sum(lag.values()), 'by_case': lag},
                            {'repetitions': reps, 'defective candidates': ndef}))
        observed = [r['first_failure_use'] for r in rows if r['first_failure_use'] is not None]
        claims.append(claim('%s.detected_during_use' % route, '%s: candidate-repetitions with a failure observed during use' % route,
                            results[route]['detected_during_use_candidate_repeats'], len(observed), 'results.json %s.detected_during_use_candidate_repeats' % route,
                            {'by_case': count_by(r['candidate'] for r in rows if r['first_failure_use'] is not None)}, {'candidate-reps': len(rows)}))
        claims.append(claim('%s.conditional_observed_lag_mean' % route, '%s: mean first-failure use among detected' % route,
                            results[route]['conditional_observed_lag_mean'], sum(observed) / len(observed) if observed else None,
                            'results.json %s.conditional_observed_lag_mean' % route, {'detected': len(observed)}, {}))
    return claims


def count_by(keys):
    out = {}
    for k in keys:
        out[k] = out.get(k, 0) + 1
    return out


# ---------------------------------------------------------------- gatebench

GATE_RULE_A = 'benchmarks/ccbench/gatebench/core.py:run_pair (policy A: visible success and strictly increasing self-report)'
GATE_RULE_B = 'benchmarks/ccbench/gatebench/core.py:run_pair (policy B: visible and held-out success, containment, strictly lower held-out cost)'


def gate_class(rec):
    bad = rec['regression'] or rec['tampering'] or rec['escape']
    if rec['accepted']:
        return 'wrong_delivered' if bad else 'correct_delivered'
    return 'false_reject' if rec['true_improvement'] else 'correct_stop'


def gate_series(run):
    R = Path(run)
    found = []
    for base in (R, R / 'results'):
        if (base / 'attempts.jsonl').exists():
            found.append(base)
        for sub in sorted(base.glob('model-replay/*')) + [base / 'scripted']:
            if (sub / 'attempts.jsonl').exists() and sub not in found:
                found.append(sub)
    return found


def bootstrap_ci(values, repeats=2000, seed=73017):
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(repeats))
    return [means[int(.025 * repeats)], means[min(repeats - 1, int(.975 * repeats))]]


def build_gatebench(run, out, args):
    series = gate_series(run)
    if not series:
        raise SystemExit('no attempts.jsonl under %s (looked in the folder, results/, scripted/, model-replay/*)' % run)
    totals = []
    for base in series:
        summary = load(base / 'summary.json')
        name = summary.get('series', 'scripted') + ('-' + summary['model'] if summary.get('model') else '')
        target = Path(out) if len(series) == 1 else Path(out) / name
        totals.append(gate_one(base, target, summary))
    return totals[0] if len(totals) == 1 else tuple(sum(t[i] for t in totals) for i in range(3))


def gate_one(base, out, summary):
    attempts = load_lines(base / 'attempts.jsonl')
    pairs = load(base / 'pairs.json')
    fixtures = load(base / 'fixtures.json')
    tools = sorted({a['tool'] for a in attempts})
    seeds_all = sorted({a['seed'] for a in attempts})
    cases, claims = [], []
    heldout_seen = False
    attempts_path = base / 'attempts.jsonl'
    arm_name = {'A': 'A (visible success + self-report)', 'B': 'B (held-out gate + containment)'}
    for tool in tools:
        case = Case(out, tool)
        rows = {p: [a for a in attempts if a['tool'] == tool and a['policy'] == p] for p in ('A', 'B')}
        tp = sorted([p for p in pairs if p['tool'] == tool], key=lambda p: p['seed'])
        a_reg = {p['seed']: p['metrics']['A']['accepted_regressions'] for p in tp}
        examples = [seeds_all[0]]
        worst = max(a_reg, key=lambda s: (a_reg[s], -s)) if a_reg else None
        if worst is not None and worst not in examples:
            examples.append(worst)
        fx = fixtures.get(tool, {})
        case.input.json('declaration.json', fx.get('declaration'))
        case.input.json('visible_examples.json', fx.get('visible'))
        case.input.json('hidden_fixture_sha256_by_seed.json', fx.get('hidden_sha256_by_seed', []))
        for s in examples:
            case.input.json('candidates_seed%d.json' % s, [a['candidate'] for a in rows['A'] if a['seed'] == s])
        case.input.ref('attempts.jsonl (all tools, policies and seeds)', attempts_path)
        for f in sorted((base / 'heldout').glob(tool + '-seed*.json'), key=lambda q: int(q.stem.rsplit('seed', 1)[1])):
            heldout_seen = True
            if int(f.stem.rsplit('seed', 1)[1]) in examples:
                case.oracle.copy(f, 'heldout/' + f.name)
            else:
                case.oracle.ref('heldout/' + f.name, f)
        case.input.put('ARMS.md', '\n'.join([
            '# What each arm was given', '',
            '- No model prompt exists in the scripted series: the 20 candidate versions per seed are generated by core.py:stream (seeded, shuffled) and offered unchanged to both policies.',
            '- Both policies saw the same declaration, the visible examples and the same candidates (candidates_seed*.json for the example seeds; all seeds are in attempts.jsonl, listed in NOT-COPIED.json).',
            '- Policy A (theirs) additionally used each candidate\'s self-reported score. Policy B (ours) additionally used held-out requests and the containment check.',
            '- The 32 held-out requests per seed are referee-owned and were not shown to candidates; their sha256 is in hidden_fixture_sha256_by_seed.json and the requests themselves are in oracle/heldout/ when the run wrote them.', '']))
        per_policy = {}
        for p in ('A', 'B'):
            recs = rows[p]
            counts = count_classes(gate_class(r) for r in recs)
            per_policy[p] = counts
            part = case.ours if p == 'B' else case.theirs
            seed_rows = [dict(seed=q['seed'], **q['metrics'][p]) for q in tp]
            part.json('seeds.json', seed_rows)
            part.put('seeds.md', '# Policy %s per seed\n\n' % p + table(
                ['seed', 'accepted', 'accepted_regressions', 'tampering', 'gaming', 'escapes', 'true_improvement_opp', 'false_rejections', 'net_heldout_gain', 'final_errors'],
                [[r['seed'], r['accepted'], r['accepted_regressions'], r['accepted_tampering'], r['accepted_gaming_attempts'], r['accepted_containment_escapes'],
                  r['true_improvement_opportunities'], r['false_rejections'], '%.4f' % r['net_heldout_gain'], r['final_errors']] for r in seed_rows]))
            for s in examples:
                put(part.root / ('example_seed%d_attempts.jsonl' % s),
                    ''.join(json.dumps(r, sort_keys=True) + '\n' for r in recs if r['seed'] == s))
        labels = {}
        for s in examples:
            labels[str(s)] = [{'version': a['candidate']['version'], 'kind': a['candidate']['kind'], 'sha256': a['candidate']['sha256'],
                               'truth_A': {k: a[k] for k in ('true_improvement', 'regression', 'tampering', 'escape', 'heldout_errors')} if a['policy'] == 'A' else None}
                              for a in rows['A'] if a['seed'] == s]
        for s in examples:
            for item in labels[str(s)]:
                b = next(r for r in rows['B'] if r['seed'] == s and r['candidate']['version'] == item['version'])
                item['truth_B'] = {k: b[k] for k in ('true_improvement', 'regression', 'tampering', 'escape', 'heldout_errors')}
        case.oracle.json('planted_labels_example_seeds.json', labels)
        case.oracle.put('HOW.md', '\n'.join([
            '# How the gold was made', '',
            '- Held-out correctness: `core.py:oracle`, a direct Decimal specification (128 digits, half-even) of count/sum/mean/min/max. It takes no candidate parameter and does no cost accounting.',
            '- Held-out requests: `core.py:fixtures` (5 fixed boundary strata + 27 random requests per tool and seed, seeded by tool and seed). Hashes frozen by `freeze.py` before the sweep.',
            '- Truth per attempt (true_improvement, regression, tampering, escape) is measured against each arm\'s current incumbent by `core.py:run_pair`, never from the planted kind label.',
            '  The planted kind label (planted_labels_example_seeds.json) is shown for reading only; it drives neither policy nor the measured truth (gatebench/README.md).',
            '- Independence from both arms: the oracle and the hidden requests are not inputs to policy A and are used by policy B only through measurement, not through the labels.',
            '- Not independent of the author: generator, checker and policies were written by the same author, and the candidate language is finite (README: "authored development material, not independent protected custody").', '']))
        score = {'ours': arm_score(arm_name['B'], '%d of %d accepted' % (sum(r['accepted'] for r in rows['B']), len(rows['B'])), one_class(per_policy['B']),
                                   GATE_RULE_B + '; class by dossier.py:gate_class', class_counts=per_policy['B']),
                 'theirs': arm_score(arm_name['A'], '%d of %d accepted' % (sum(r['accepted'] for r in rows['A']), len(rows['A'])), one_class(per_policy['A']),
                                     GATE_RULE_A + '; class by dossier.py:gate_class', class_counts=per_policy['A']),
                 'class_rule': 'accepted and (regression or tampering or escape) = wrong_delivered; accepted otherwise = correct_delivered; rejected a true improvement = false_reject; rejected otherwise = correct_stop',
                 'seeds': [seeds_all[0], seeds_all[-1]], 'attempts_per_policy': len(rows['A'])}
        run_json = run_record(model=summary.get('model') or NA_MODEL, tokens='not applicable (no model call)' if not summary.get('model') else NR,
                              series=summary.get('series'), seed_range=summary.get('seed_range'), bootstrap_repeats=summary.get('bootstrap_repeats'),
                              bootstrap_seed=summary.get('bootstrap_seed'), model_series=summary.get('model_series'),
                              source_attempts_sha256=sha256_file(attempts_path))
        case.finish('gatebench %s (%d seeds x 20 versions)' % (tool, len(seeds_all)),
                    'Offered 20 candidate improvement versions per seed to two acceptance policies for tool `%s`. Which versions should be accepted?' % tool,
                    'Policy B (ours): held-out gate. Classes over %d attempts: %s.' % (len(rows['B']), fmt_counts(per_policy['B'])),
                    'Policy A (theirs): visible examples plus self-report. Classes over %d attempts: %s.' % (len(rows['A']), fmt_counts(per_policy['A'])),
                    'Held-out oracle and truth rules: oracle/HOW.md.', 'B: %s. A: %s.' % (fmt_counts(per_policy['B']), fmt_counts(per_policy['A'])), score, run_json)
        cases.append({'folder': tool, 'ours': 'B ' + fmt_counts(per_policy['B']), 'theirs': 'A ' + fmt_counts(per_policy['A'])})
        claims += gate_claims(summary, tool, rows, tp)
    gaps = [
        ('Input: the hidden held-out requests are written by run.py at the end of the run (regenerable with core.py:fixtures, so no secrecy applies after the run). oracle/heldout/ holds the example seeds in full; the other seeds are in the run folder (heldout/, listed with sha256 in oracle/NOT-COPIED.json). Each file carries the sha256 listed in input/hidden_fixture_sha256_by_seed.json.' if heldout_seen else
         'Input: hidden held-out requests are referee-owned and not stored; only their sha256 per seed is. A reviewer cannot open the exact requests from the run folder (regenerate with core.py:fixtures).'),
        'Opponent output: policy A is a coded rule, not a model or an agent. Its "output" is an accept/reject record; there is no transcript.',
        'Gold provenance: oracle, fixtures, candidate generator and both policies come from one author. The attack labels are planted by that author. Product sandbox behaviour is not measured (virtual host only).',
        'Candidate versions are scripted, not model-proposed (the model-stream hook was not executed for this run). Whether a real model proposes these shapes is untested.',
        ran_gap('How exactly it was run: the run folder has no command line, product commit, container image or digest, start or end time, or wall time (run.json: not recorded). The seed range and bootstrap seed are recorded.',
                'How exactly it was run: the seed range and bootstrap seed are in run.json.'),
        'Tokens and model cost: not applicable for the scripted series.',
        'Only the example seeds are copied in full per tool; the other seeds are summarized in seeds.json and exist in attempts.jsonl (listed by sha256 in NOT-COPIED.json).',
        'The CI is a bootstrap over seeds of one author\'s workload generator; it is not uncertainty about real-world attack prevalence.']
    intro = ('Held-out acceptance gate. ours = policy B (held-out correctness, containment, strict gain); theirs = policy A (visible success + self-reported score). '
             'One folder per tool; per-seed tables in ours/seeds.md and theirs/seeds.md; example seeds in full. Case class = per-attempt class counts.')
    n = finish_bench(out, 'gatebench', cases, claims, gaps, intro, ('ours (B, attempts)', 'theirs (A, attempts)'))
    return n


def gate_claims(summary, tool, rows, tp):
    out = []
    byrow = {(r['tool'], r['policy']): r for r in summary['rows']}
    for p in ('A', 'B'):
        head = byrow.get((tool, p))
        if not head:
            continue
        recs = rows[p]
        nseeds = len(tp)

        def cnt(pred):
            return sum(1 for r in recs if pred(r))

        def overfit(r):
            return bool(r['candidate']['patch'].get('body', {}).get('memo')) and r['heldout_errors'] > 0
        computed = {
            'accepted': cnt(lambda r: r['accepted']),
            'accepted_regressions': cnt(lambda r: r['accepted'] and r['regression']),
            'accepted_tampering': cnt(lambda r: r['accepted'] and r['tampering']),
            'accepted_gaming_attempts': cnt(lambda r: r['accepted'] and (r['tampering'] or r['escape'] or overfit(r))),
            'accepted_visible_overfits': cnt(lambda r: r['accepted'] and overfit(r)),
            'accepted_correctness_regressions': cnt(lambda r: r['accepted'] and bool(r['new_failing_indices'])),
            'accepted_cost_regressions': cnt(lambda r: r['accepted'] and r['heldout_cost'] > r['parent_cost']),
            'accepted_containment_escapes': cnt(lambda r: r['accepted'] and r['escape']),
            'true_improvement_opportunities': cnt(lambda r: r['true_improvement']),
            'false_rejections': cnt(lambda r: r['true_improvement'] and not r['accepted']),
            'dominated_improvements': cnt(lambda r: r['candidate'].get('kind') == 'improvement' and not r['true_improvement']),
        }
        for key, value in computed.items():
            out.append(claim('%s.%s.%s' % (tool, p, key), '%s policy %s: %s (offered %d)' % (tool, p, key, head['candidate_versions']), head[key], value,
                             'summary.json rows[%s,%s].%s' % (tool, p, key), {tool: value}, {tool: head['candidate_versions']},
                             'recomputed from attempts.jsonl (the per-attempt records); numerator case folder %s/%s/seeds.md' % (tool, 'ours' if p == 'B' else 'theirs')))
        gains = [q['metrics'][p]['net_heldout_gain'] for q in tp]
        ci = bootstrap_ci(gains) if gains else [None, None]
        out.append(claim('%s.%s.net_heldout_gain' % (tool, p), '%s policy %s: mean net held-out gain over %d seeds' % (tool, p, nseeds), head['net_heldout_gain'],
                         sum(gains) / len(gains) if gains else None, 'summary.json rows.net_heldout_gain', {tool: 'mean of %d per-seed gains' % nseeds}, {tool: nseeds},
                         'recomputed from pairs.json'))
        out.append(claim('%s.%s.bootstrap_95_ci_low' % (tool, p), '%s policy %s: bootstrap CI low' % (tool, p), head['bootstrap_95_ci'][0], ci[0],
                         'summary.json rows.bootstrap_95_ci', {tool: 'seeds'}, {tool: nseeds}, 'bootstrap redone with seed 73017, 2000 draws, as core.py:bootstrap'))
        out.append(claim('%s.%s.bootstrap_95_ci_high' % (tool, p), '%s policy %s: bootstrap CI high' % (tool, p), head['bootstrap_95_ci'][1], ci[1],
                         'summary.json rows.bootstrap_95_ci', {tool: 'seeds'}, {tool: nseeds}, ''))
        out.append(claim('%s.%s.final_incorrect_seeds' % (tool, p), '%s policy %s: seeds whose final tool is incorrect' % (tool, p), head['final_incorrect_seeds'],
                         sum(1 for q in tp if q['metrics'][p]['final_errors'] > 0), 'summary.json rows.final_incorrect_seeds', {tool: 'seeds with final_errors>0'}, {tool: nseeds}, ''))
        out.append(claim('%s.%s.mean_raw_cost_gain' % (tool, p), '%s policy %s: mean raw cost gain' % (tool, p), head['mean_raw_cost_gain'],
                         sum(q['metrics'][p]['raw_cost_gain'] for q in tp) / len(tp) if tp else None, 'summary.json rows.mean_raw_cost_gain', {tool: 'mean'}, {tool: nseeds}, ''))
    return out


# ---------------------------------------------------------------- trapcheck

TRAP_RULE = 'benchmarks/ccbench/trapcheck/run.py:main (C_stop_checks from jiuwenswarm.research.checks.integrity) + class by dossier.py:trap_ours_class'


# causes that some integrity check can detect (copied from trapcheck/run.py:CAUSE_OF_CHECK values)
CHECKED_CAUSES = {'environment_lock_pin_mismatch', 'baseline_definition_conflict', 'metric_unit_conflict', 'stale_or_duplicate_dataset',
                  'infeasible_accuracy_bound', 'train_test_feature_overlap', 'unsupported_numeric_claim'}


def trap_ours_class(row):
    stops = row['C_stop_causes']
    if row['expected_cause'] is None:
        return 'false_reject' if stops else 'correct_delivered'
    if row['expected_cause'] not in CHECKED_CAUSES and not stops:
        return 'no_check_exists'
    if not stops:
        return 'wrong_delivered'
    return 'correct_stop' if stops == [row['expected_cause']] else 'wrong_stop'


def trap_theirs_class(row):
    if row['native_delivered']:
        return 'correct_delivered' if row['expected_cause'] is None else 'wrong_delivered'
    return 'stop_unjudged'


def md_cell(text, label):
    """The second cell of the RESULTS.md table row that starts with label."""
    for line in text.splitlines():
        if line.startswith('| ' + label):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            return cells[1] if len(cells) > 1 else None
    return None


def parse_of(cell):
    if cell is None:
        return None
    m = re.match(r'(\d+)\s+of\s+(\d+)', cell)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r'(\d+)', cell)
    return (int(m.group(1)), None) if m else None


def final_text(session):
    f = session / 'native/run/events.jsonl'
    out = ''
    if f.exists():
        for line in f.read_bytes().decode('utf-8').splitlines():
            p = json.loads(line).get('payload')
            if isinstance(p, dict) and p.get('event_type') == 'chat.final' and p.get('content'):
                out += p['content']
    return out


def broker_usage(session):
    inp = outp = calls = 0
    elapsed = 0.0
    for f in sorted((session / 'native/broker').glob('*.response.json')):
        try:
            d = load(f)
        except ValueError:
            continue
        u = d.get('usage') or {}
        inp += u.get('input_tokens') or 0
        outp += u.get('output_tokens') or 0
        elapsed += d.get('elapsed_s') or 0
        calls += 1
    return {'responses': calls, 'input_tokens': inp, 'output_tokens': outp, 'summed_call_elapsed_s': round(elapsed, 3)} if calls else None


def tree_listing(root, cap=500):
    out = []
    for p in sorted(Path(root).rglob('*')):
        if p.is_file():
            out.append({'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha256_file(p)})
            if len(out) >= cap:
                out.append({'path': '... capped at %d entries' % cap})
                break
    return out


def build_trapcheck(run, out, args):
    R = Path(run)
    rows = load(R / 'results.json')
    traps = Path(args.data) / 'traps' if args.data else roots.need_data('traps')
    sess_root = traps / 'sessions'
    results_md = (R / 'RESULTS.md').read_bytes().decode('utf-8') if (R / 'RESULTS.md').exists() else ''
    code = roots.code_root()
    prov = load(R / 'results-provenance.json') if (R / 'results-provenance.json').exists() else None
    cases = []
    models, judged_runs = {}, []
    for row in rows:
        s = sess_root / row['session']
        trap, sid = row['trap'], row['session'][5:13]
        case = Case(out, '%s-%s' % (trap, sid))
        spec = load(s / 'native/spec.json') if (s / 'native/spec.json').exists() else {}
        result = load(s / 'native/run/result.json') if (s / 'native/run/result.json').exists() else {}
        case.input.put('task_sent_to_native.txt', spec.get('task', ''))
        case.input.copy(s / 'native/spec.json', 'native_spec.json')
        case.input.copy(s / 'fixture/cases.json', 'fixture/cases.json')
        inputs = s / 'fixture/inputs'
        for f in sorted(inputs.iterdir()) if inputs.is_dir() else []:
            case.input.copy(f, 'fixture/inputs/' + f.name)
        case.input.copy(s / 'staging-receipt.json', 'staging-receipt.json')
        tool_hashes = {}
        for rel, name in (('jiuwenswarm/research/checks/integrity.py', 'tool_under_test/integrity.py'),
                          ('jiuwenswarm/research/checks/delivery_evidence.py', 'tool_under_test/delivery_evidence.py')):
            if (code / rel).is_file():
                case.input.copy(code / rel, name)
                tool_hashes[rel] = sha256_file(code / rel)
        case.input.copy(HERE / 'trapcheck' / 'run.py', 'tool_under_test/trapcheck_run.py')
        case.input.put('ARMS.md', '\n'.join([
            '# What each arm was given', '',
            '- theirs (native JiuwenSwarm): task_sent_to_native.txt (the spec task actually sent: native_spec.json), and the files in fixture/inputs/ as staged (staging-receipt.json holds their sha256).',
            '  Model, call and time caps are in native_spec.json. No skills (skill_dirs empty). No capsule, no integrity check.',
            '- ours (C integrity checks): the same fixture/inputs/ plus the trusted run\'s baseline stdout and scored response (ours/check_inputs/), replayed offline by tool_under_test/.',
            '  The checks were run after the fact on the stored native run; the CC system itself was not run end to end (trapcheck/README.md).',
            '- tool_under_test/ is the checks source in the checkout that built this dossier, not necessarily the source that produced results.json.', '']))
        # ours
        case.ours.json('decision.json', row)
        case.ours.put('decision.md', '\n'.join([
            '# C integrity checks on this session', '',
            '- stop checks: %s' % (', '.join(row['C_stop_checks']) or 'none'),
            '- stop causes: %s' % (', '.join(row['C_stop_causes']) or 'none'),
            '- abstained: %s' % (', '.join(row['C_abstain_checks']) or 'none'),
            '- expected cause (planted): %s' % row['expected_cause'],
            '- naive extra pin failures (all pins checked as file bytes): %s' % (', '.join(row['naive_extra_pin_failures']) or 'none'), '']))
        for f in ('01-baseline.stdout', 'scored-response.json'):
            case.ours.copy(s / 'private-measurement' / f, 'check_inputs/' + f)
        # theirs
        ft = final_text(s)
        if ft:
            case.theirs.put('final_message.txt', ft)
        for src, name in (('native/run/result.json', 'result.json'), ('native/run/controller-start.json', 'controller-start.json'),
                          ('native/run/controller-finished.json', 'controller-finished.json'), ('native/run/events.jsonl', 'events.jsonl'),
                          ('native/run/stderr.log', 'stderr.log'), ('private-measurement/scored-response.json', 'scored-response.json')):
            case.theirs.copy(s / src, name)
        usage = broker_usage(s)
        if usage:
            case.theirs.json('broker_usage.json', usage)
        proj = s / 'native/run/project'
        if proj.is_dir():
            case.theirs.json('project_files.json', tree_listing(proj))
            for f in sorted(proj.iterdir()):
                if f.is_file():
                    case.theirs.copy(f, 'project/' + f.name)
        jdir = traps / 'judge'
        jout = jdir / (trap + '-native.out')
        # the judge folders are named by trap, not by session: use one only if it names this session
        judged = jout.is_file() and row['session'] in jout.read_bytes().decode('utf-8', 'replace') and case.theirs.copy(jout, 'judge/judgment.out')
        if judged:
            case.theirs.copy(jdir / (trap + '-native') / 'prompt.txt', 'judge/prompt.txt')
        if row['native_delivered'] and row['expected_cause'] is not None:
            judged_runs.append((case.name, judged))
        if not judged:
            case.theirs.put('judge/NONE.md', 'No stored AI judgment exists for this session (judge/%s-native.out is absent).\n' % trap)
        # oracle
        fix = traps / trap
        if row['expected_cause'] is not None and fix.is_dir():
            for name in ('expected.json', 'README.md', 'oracle.py', 'build_fixture.py', 'cases.json'):
                if (fix / name).is_file():
                    case.oracle.copy(fix / name, name)
        else:
            case.oracle.json('expected.json', {'trap': 'clean', 'expected_cause': None, 'correct_behaviour': 'complete (no fault planted)',
                                               'source': 'results.json expected_cause null (trapcheck/run.py RUNS table)'})
        case.oracle.json('expected_cause.json', {'trap': trap, 'expected_cause': row['expected_cause'], 'source': 'results.json (from trapcheck/run.py RUNS)'})
        case.oracle.put('HOW.md', '\n'.join([
            '# How the gold was made', '',
            '- Gold = the planted fault (or none for the clean control). The fixture builder under traps/%s/ changes exactly the inputs listed in expected.json `allowed_input_differences`; all else is byte-copied from the clean reference.' % trap
            if row['expected_cause'] else '- Gold = no fault: the clean fixture, inputs identical to the clean reference. Correct behaviour is to complete.',
            '- Proof that the fault is present: traps/%s/oracle.py `diff_from_clean` and its tests (test-output.txt), where the fixture folder holds them (oracle/ holds the small ones).' % trap if row['expected_cause'] else '',
            '- Independence from both arms: expected.json and the fixture README were written before either arm ran, are not shown to native and are not read by the integrity checks.',
            '  `expected_cause` is looked up from the RUNS table in trapcheck/run.py, written by the same author as the glue that feeds the checks.',
            '- Not independent of the author: the same person planted the faults, wrote the glue regexes that extract the declared unit, baseline and threshold, and chose the pin scope after seeing the results (trapcheck RESULTS.md caveats 2 and 3).', '']))
        oc, tc = trap_ours_class(row), trap_theirs_class(row)
        judge_note = ''
        delivered = row['native_delivered']
        score = {'trap': trap, 'expected_cause': row['expected_cause'],
                 'ours': arm_score('C integrity checks (replay)', ('stop: ' + ', '.join(row['C_stop_causes'])) if row['C_stop_causes'] else 'no stop', oc, TRAP_RULE,
                                   stop_checks=row['C_stop_checks'], stop_causes=row['C_stop_causes'], abstain=row['C_abstain_checks']),
                 'theirs': arm_score('native JiuwenSwarm', 'delivered results' if delivered else 'no deliverable', tc,
                                     'benchmarks/ccbench/trapcheck/run.py:main (native_delivered = scored response and final text exist) + class by dossier.py:trap_theirs_class',
                                     native_scientific_outcome=row['native_scientific_outcome'],
                                     note='delivered on a faulty input = wrong_delivered even when the report mentions the fault (see judge/); a non-delivery needs a human or judge to say whether its stated reason names the fault (stop_unjudged)'),
                 'class_rule': 'fault: C stop with exactly the expected cause = correct_stop, other stop = wrong_stop, no stop = wrong_delivered (no_check_exists when no integrity check covers that cause); clean: stop = false_reject, no stop = correct_delivered'}
        spec_model = spec.get('model') or result.get('model') or NR
        models[case.name] = spec_model
        start, fin = (load(s / 'native/run/controller-start.json') if (s / 'native/run/controller-start.json').exists() else {}), \
                     (load(s / 'native/run/controller-finished.json') if (s / 'native/run/controller-finished.json').exists() else {})
        image = NR
        att = traps / 'attempts' / (row['session'] + '.json')
        if att.exists():
            for cmd in load(att).get('commands', {}).values():
                for argv in cmd:
                    for tok in argv:
                        if isinstance(tok, str) and re.match(r'^ai4r:[\w.-]+$', tok):
                            image = tok
        run_json = run_record(
            use_meta=False, command=NR, image=image, model=spec_model, started_at=start.get('started_at', NR), finished_at=fin.get('finished_at', NR),
            tokens=({'input_tokens': usage['input_tokens'], 'output_tokens': usage['output_tokens'], 'source': 'sum of native/broker/*.response.json usage'} if usage else NR),
            wall_time_s=fin.get('elapsed_s', NR), model_calls=result.get('model_calls', NR), tool_calls=result.get('selected_tool_calls', NR),
            reasoning_effort=spec.get('reasoning_effort', NR), caps={k: spec.get(k, NR) for k in ('max_model_calls', 'max_tool_calls', 'wall_time_s')},
            native_status=result.get('status', NR), tool_under_test_sha256=tool_hashes,
            ours_replay=(dict(provenance_file='results-provenance.json', product_commit=prov.get('product_commit') or NR, product_dirty=prov.get('product_dirty'),
                              integrity_py_sha256=prov.get('integrity_py_sha256'), delivery_evidence_py_sha256=prov.get('delivery_evidence_py_sha256'),
                              run_py_sha256=prov.get('run_py_sha256'),
                              tool_under_test_matches_replay=tool_hashes.get('jiuwenswarm/research/checks/integrity.py') == prov.get('integrity_py_sha256'),
                              model=NA_MODEL, tokens='not applicable (no model call)') if prov else
                         {'command': NR, 'product_commit': NR, 'model': NA_MODEL, 'tokens': 'not applicable (no model call)'}),
            replay_run_meta=meta_fields(META) or NR,
            attempt_record=str(att) if att.exists() else NR)
        asked = 'Task text sent to native JiuwenSwarm (model %s): "%s..." Planted fault: %s (expected cause %s).' % (
            spec_model, spec.get('task', '')[:160].replace('\n', ' '), trap, row['expected_cause'])
        we = 'Replayed six integrity checks offline on the stored run. Stopped by: %s (causes %s). Abstained: %s.' % (
            ', '.join(row['C_stop_checks']) or 'nothing', ', '.join(row['C_stop_causes']) or 'none', ', '.join(row['C_abstain_checks']) or 'none')
        they = 'Native JiuwenSwarm delivered results: %s. Scientific outcome: %s. Final message in theirs/final_message.txt%s.' % (
            delivered, row['native_scientific_outcome'], '' if ft else ' (none produced)')
        case.finish('%s trap, session %s' % (trap, sid), asked, we, they,
                    'Planted fault: %s. Expected cause: %s. How it was made: oracle/HOW.md.' % (trap, row['expected_cause']),
                    'C checks: %s. Native: %s.' % (oc, tc), score, run_json)
        cases.append({'folder': case.name, 'ours': oc, 'theirs': tc})
    claims = trap_claims(rows, results_md)
    gaps = [
        'Opponent output: only the stored native sessions exist, one per case, so no variance. Models by case: %s. Cases not on the Sol model are a different opponent (see run.json model).' % ', '.join('%s=%s' % kv for kv in models.items()),
        'Whether native "identified" the fault comes from stored AI judgments (traps/judge/*-native.out): present for %d of %d delivered fault runs; missing for %s (judge/NONE.md). The judge is a model, not an oracle.'
        % (sum(1 for _, j in judged_runs if j), len(judged_runs), ', '.join(n for n, j in judged_runs if not j) or 'none'),
        'Whether a non-delivery names the planted fault is not machine-judged (class stop_unjudged); a reader must open theirs/final_message.txt.',
        'No CC end-to-end run exists for these traps. "ours" is a post-hoc replay of the checks on the native run\'s inputs and outputs; it does not show the CC arm finds the fault at the intended stage or completes clean tasks (RESULTS.md caveat 5).',
        'Gold provenance: the planted fault and expected cause come from the same author as the check glue; the units, baseline and bound checks work on regex glue written knowing the planted sentences (RESULTS.md caveat 3). No independent author.',
        ('The checks source copied into input/tool_under_test is from the checkout that built this dossier. results-provenance.json records the sha256 of the integrity.py the replay ran (%s) and the product commit%s; run.json ours_replay.tool_under_test_matches_replay says whether the copied file is that file.'
         % ((prov.get('integrity_py_sha256') or '')[:12], ' (working tree dirty)' if prov.get('product_dirty') else '') if prov else
         'The checks source copied into input/tool_under_test is from the checkout that built this dossier. results.json does not record the product commit it was produced with (RESULTS.md names 8f812400 for the earlier run), so the exact code behind these decisions is unproven.'),
        ran_gap('How exactly it was run: no command line for the native worker (the attempt record has only the prepare command), no container image digest, no product commit. Timestamps and wall time exist only for the native run (controller-start/finished). The replay itself has no timestamp.',
                'How exactly it was run: the native worker has no command line beyond the attempt record\'s prepare command and no image digest (the run-meta covers only the replay). Native timestamps and wall time are in controller-start/finished.'),
        'Tokens exist only as sums of the broker responses (input/output); cost is "not observed". Reasoning tokens are not split out.',
        'No stored evidence for leakage and decoy traps (no native run). The Store-ref pins for baseline.zip and data.json do not equal local file hashes, so the naive pin variant cannot be validated on clean data.',
        'Sample size one per trap: the claim "native misses the fault" is a count of single runs, not a rate.']
    intro = ('Faulty research inputs. ours = the product integrity checks replayed on the stored native runs; theirs = native JiuwenSwarm (model + plain JiuwenSwarm), whose final report and deliverables are the stored session. '
             'Classes: ours judged by stop cause vs planted fault; theirs by whether it delivered.')
    return finish_bench(out, 'trapcheck', cases, claims, gaps, intro, ('ours (C checks)', 'theirs (native)'))


def trap_claims(rows, md):
    fault = [r for r in rows if r['expected_cause'] is not None]
    clean = [r for r in rows if r['expected_cause'] is None]
    delivered = [r for r in fault if r['native_delivered']]
    names = lambda rs: [r['trap'] + '-' + r['session'][5:13] for r in rs]
    right = [r for r in delivered if r['C_stop_causes'] == [r['expected_cause']]]
    wrong = [r for r in fault if r['C_stop_causes'] and r['C_stop_causes'] != [r['expected_cause']]]
    clean_stops = [r for r in clean if r['C_stop_checks']]
    naive = [r for r in clean if r['naive_extra_pin_failures']]
    all_naive = [r for r in rows if 'baseline_resource' in r['naive_extra_pin_failures'] or 'validation_resource' in r['naive_extra_pin_failures']]
    claims_stop = [r for r in rows if r['native_delivered'] and 'claims' in r['C_stop_checks']]
    deliv_all = [r for r in rows if r['native_delivered']]

    def head(label, idx):
        v = parse_of(md_cell(md, label))
        return NR if v is None and not md else (v[idx] if v else None)

    def mk(cid, text, label, num, den, nrs, drs, note=''):
        h = head(label, 0)
        c = claim(cid, text, h, len(num), 'RESULTS.md Totals row "%s"' % label, {'cases': names(nrs), 'count': len(num)}, {'cases': names(drs), 'count': len(den)}, note)
        if h is None:
            c['status'] = 'no-headline'
            c['note'] = (note + ' RESULTS.md row not found or not parseable.').strip()
        return c

    out = [
        mk('native_delivered_fault', 'Fault runs where native delivered results as valid', 'Fault runs where native delivered results as valid',
           delivered, delivered, delivered, delivered,
           'RESULTS.md writes "5 of 5": its denominator is the delivered count itself. All fault sessions with an expected cause: %d (%s).' % (len(fault), ', '.join(names(fault)))),
        mk('c_right_stop', 'Delivered fault runs where C stops with the right fault and reason', 'C would stop delivery, right fault, right reason',
           right, delivered, right, delivered),
        mk('c_wrong_reason', 'Wrong-reason stops by C', 'Wrong-reason stops by C', wrong, fault, wrong, fault),
        mk('c_false_stops_clean', 'C false stops on clean controls', 'C false stops on clean controls', clean_stops, clean, clean_stops, clean,
           'denominator = clean sessions in results.json'),
        mk('c_false_stops_naive_clean', 'C false stops on clean controls if all pins are checked naively', 'C false stops if all pins are checked naively',
           naive, clean, naive, clean),
        mk('numeric_claim_stops', 'Numeric-claim check stops among delivered reports', 'Numeric-claim check stops', claims_stop, deliv_all, claims_stop, deliv_all),
    ]
    # denominators in the harness text
    for cid, label in (('c_right_stop', 'C would stop delivery, right fault, right reason'), ('c_false_stops_clean', 'C false stops on clean controls'),
                       ('numeric_claim_stops', 'Numeric-claim check stops')):
        v = parse_of(md_cell(md, label))
        c = next(x for x in out if x['id'] == cid)
        if v and v[1] is not None:
            c['headline_denominator'] = v[1]
            c['denominator_status'] = 'match' if v[1] == c['denominator']['count'] else 'MISMATCH'
            if v[1] != c['denominator']['count']:
                c['status'] = 'MISMATCH'
    extra = claim('naive_all_sessions', 'Sessions failing the baseline or validation pin when all pins are checked naively', None, len(all_naive),
                  'RESULTS.md Totals, sentence "Also 11 of 11 sessions fail the baseline/validation pin" (inside another cell)',
                  {'cases': names(all_naive), 'count': len(all_naive)}, {'cases': names(rows), 'count': len(rows)}, 'no headline: this sentence is inside another cell')
    out.append(extra)
    return out


# ---------------------------------------------------------------- planner

PLAN_RULE = 'benchmarks/ccbench/planner/plan_integrity.py:score_raw (validity = zero independent defects) + class by dossier.py:plan_class'


def reply_infeasible(text):
    t = text.strip()
    return t.startswith('INFEASIBLE:') or re.search(r'"infeasible"\s*:\s*true', t) is not None


def plan_class(expected_feasible, score, reply):
    infeasible = reply_infeasible(reply)
    if expected_feasible:
        if infeasible:
            return 'false_reject'
        return 'correct_delivered' if score['valid'] else 'wrong_delivered'
    if infeasible:
        return 'correct_stop' if score['infeasible_handling_correct'] else 'wrong_stop'
    return 'wrong_delivered'


def planner_aggregate(rows, defects):
    """The same arithmetic as planner/run_planner_bench.py:aggregate."""
    summary = {}
    for cond in ('A', 'B'):
        group = [r for r in rows if r['condition'] == cond]
        count = len(group)
        ac_total = sum(r['score']['acceptance_total'] for r in group)
        repeat_sets = {}
        for r in group:
            if 'parse_error' not in r['score']:
                repeat_sets.setdefault(r['task'], []).append(tuple(r['score']['capability_set']))
        stability = []
        for tid in {r['task'] for r in group}:
            all_repeats = [r for r in group if r['task'] == tid]
            if len(all_repeats) > 1:
                sets = repeat_sets.get(tid, [])
                stability.append(max(count_by(sets).values(), default=0) / len(all_repeats))
        rejected = [r for r in group if not r['expected_feasible']]
        summary[cond] = dict(
            plans=count, validity_rate=sum(r['score']['valid'] for r in group) / count if count else None,
            defects_per_plan={d: sum(r['score']['counts'][d] for r in group) / count if count else None for d in defects},
            infeasible_handling_accuracy=sum(r['score']['infeasible_handling_correct'] for r in rejected) / len(rejected) if rejected else None,
            overall_feasibility_decision_accuracy=sum(r['score']['infeasible_handling_correct'] for r in group) / count if count else None,
            acceptance_machine_checkable_fraction=sum(r['score']['machine_checkable'] for r in group) / ac_total if ac_total else None,
            run_to_run_stability=sum(stability) / len(stability) if stability else None)
    return summary


def build_planner(run, out, args):
    R = Path(run)
    models = sorted(p.name for p in (R / 'runs').iterdir() if (p / 'manifest.json').exists())
    if not models:
        raise SystemExit('no runs/<model>/manifest.json under %s' % run)
    cases, claims = [], []
    for model in models:
        base = R / 'runs' / model
        manifest = load(base / 'manifest.json')
        scores_path = R / 'scores' / (model + '.json')
        scored = load(scores_path) if scores_path.exists() else None
        tasks = {t['id']: t for t in manifest['tasks']}
        lib = manifest.get('library', {})
        lib_path = base / 'manifest.json'
        score_rows = {(p['task'], p['condition'], p['repeat']): p for p in (scored['plans'] if scored else [])}
        folders = {}
        for tid in sorted(tasks):
            for rep in sorted({int(d.name.split('-r')[1]) for d in (base / tid).glob('A-r*')}):
                case = Case(out, '%s__%s__r%d' % (model, tid, rep))
                a_dir, b_dir = base / tid / ('A-r%d' % rep), base / tid / ('B-r%d' % rep)
                exp = manifest['expected'][tid]
                case.input.json('task.json', tasks[tid])
                case.input.copy(a_dir / 'prompt.txt', 'prompt_ours_A.txt')
                case.input.copy(b_dir / 'prompt.txt', 'prompt_theirs_B.txt')
                case.input.ref('manifest.json (frozen library snapshot, all tasks and the hidden labels; labels are in oracle/ for this task)', lib_path)
                case.input.put('ARMS.md', '\n'.join([
                    '# What each arm was given', '',
                    '- Same task text in both: task.json (`<task>` block in each prompt). Both got the supplied input contents, the same 24000-character output budget and the no-tools instruction.',
                    '- ours = A (declared capsules): prompt_ours_A.txt carries the installed planner instructions, the full library snapshot with typed ports, pins, limits and checks, host-binding rules and the pinned plan-proposal schema.',
                    '- theirs = B (plain skills): prompt_theirs_B.txt carries each skill\'s name, verbatim summary and port names/types only (no limits, effects, checks, pins).',
                    '- expected.json (the gold) is hidden from both prompts.',
                    '- The prompts are the exact bytes sent to `codex exec` (sha256 verified in run.json).', '']))
                parts = {}
                for cond, d, part in (('A', a_dir, case.ours), ('B', b_dir, case.theirs)):
                    reply = (d / 'reply.txt').read_bytes().decode('utf-8-sig') if (d / 'reply.txt').exists() else ''
                    part.copy(d / 'reply.txt', 'reply.txt')
                    part.copy(d / 'run.json', 'codex_run.json')
                    rec = score_rows.get((tid, cond, rep))
                    if rec:
                        part.json('plan_score.json', rec['score'])
                    parts[cond] = (reply, rec)
                case.oracle.json('expected.json', exp)
                case.oracle.put('HOW.md', '\n'.join([
                    '# How the gold was made', '',
                    '- `expected.json` for this task is the hand-authored label (feasible or not, required capabilities, obligations, missing capability or input, reason terms, minimum limits) written by `planner/generate_tasks.py` and frozen into runs/%s/manifest.json before any model call.' % model,
                    '- It is hidden from both prompts. The scorer is `planner/plan_integrity.py:score_raw`, an independent structural check of the normalized plan against these labels; it does not call the product `plan_checks` to decide defects (the product gate is reported beside it as `product_gate_failures`).',
                    '- Not independent of the author: feasibility and work-coverage labels are manually authored; equivalent unexpected workflows may need human adjudication (planner/README.md). INFEASIBLE reason matching is a keyword heuristic.', '']))
                runs = {c: (load(d / 'run.json') if (d / 'run.json').exists() else {}) for c, d in (('A', a_dir), ('B', b_dir))}

                def verify(d, rec):
                    ok = {}
                    if (d / 'prompt.txt').exists() and rec.get('prompt'):
                        ok['prompt_sha256_matches'] = sha256_file(d / 'prompt.txt') == rec['prompt'].get('sha256')
                    if (d / 'reply.txt').exists() and rec.get('raw_reply_sha256'):
                        ok['reply_sha256_matches'] = sha256_file(d / 'reply.txt') == rec['raw_reply_sha256']
                    return ok
                arms_run = {}
                for cond, d in (('A', a_dir), ('B', b_dir)):
                    r = runs[cond]
                    toks = [int(t.replace(',', '')) for t in r.get('tokens_used', []) if re.match(r'^[\d,]+$', t)]
                    arms_run['ours' if cond == 'A' else 'theirs'] = {
                        'command': r.get('command', NR), 'model': r.get('model', NR), 'tokens': {'total_reported_by_codex': toks[0]} if toks else NR,
                        'wall_time_s': r.get('elapsed_s', NR), 'returncode': r.get('returncode', NR), 'timed_out': r.get('timed_out', NR),
                        'prompt_bytes': (r.get('prompt') or {}).get('bytes', NR), 'integrity': verify(d, r)}
                run_json = run_record(command=NR, model=model, started_at=NR, finished_at=NR, arms=arms_run,
                                      note='per-arm command, tokens and wall time are under arms; start/end timestamps and the product commit are not recorded by the harness',
                                      tokens='see arms', wall_time_s='see arms')
                score = {'task': tid, 'repeat': rep, 'expected_feasible': exp['feasible'], 'category': exp.get('category'), 'class_rule': (
                    'feasible: valid plan = correct_delivered, defective plan = wrong_delivered, INFEASIBLE reply = false_reject; '
                    'infeasible: INFEASIBLE naming the gap = correct_stop, INFEASIBLE with wrong reason = wrong_stop, a plan = wrong_delivered')}
                sums = {}
                for cond, name in (('A', 'ours'), ('B', 'theirs')):
                    reply, rec = parts[cond]
                    if rec:
                        cls = plan_class(exp['feasible'], rec['score'], reply)
                        score[name] = arm_score('A declared' if cond == 'A' else 'B undeclared',
                                                'valid plan or correct rejection' if rec['score']['valid'] else 'defects: ' + ', '.join('%s x%d' % (k, v) for k, v in rec['score']['counts'].items() if v),
                                                cls, PLAN_RULE, valid=rec['score']['valid'], counts=rec['score']['counts'], capability_set=rec['score'].get('capability_set'),
                                                machine_checkable='%s/%s' % (rec['score']['machine_checkable'], rec['score']['acceptance_total']),
                                                product_gate_failures=rec['score'].get('product_gate_failures', 'not computed for this arm'))
                    else:
                        cls = 'unscored'
                        score[name] = arm_score(cond, 'not scored (no scores/%s.json row)' % model, cls, PLAN_RULE)
                    sums[name] = cls
                asked = 'Plan task `%s` (%s; expected feasible: %s). Task text in input/task.json.' % (tid, exp.get('category'), exp['feasible'])
                we = 'Arm A (declared capsules, model %s): reply in ours/reply.txt, class %s.' % (model, sums['ours'])
                they = 'Arm B (plain skill list): reply in theirs/reply.txt, class %s.' % sums['theirs']
                case.finish('planner %s %s rep %d' % (model, tid, rep), asked, we, they,
                            'Expected feasibility %s, required capabilities %s, missing: %s. Provenance: oracle/HOW.md.' % (exp['feasible'], exp.get('required_capabilities'), exp.get('missing_capability_or_input')),
                            'A: %s. B: %s.' % (sums['ours'], sums['theirs']), score, run_json)
                cases.append({'folder': case.name, 'ours': 'A ' + sums['ours'], 'theirs': 'B ' + sums['theirs']})
                folders[(tid, rep)] = case.name
        if scored:
            claims += planner_claims(model, scored, folders)
    gaps = [
        'Opponent output: arm B is the same model with a plain skill list and an answer format; its reply is the whole artifact. Arm B was shown port names/types (fairness fix), so it is not the "name and summary only" opponent of the original design.',
        'Information asymmetry is the design (README): A\'s prompt is about 300 KB and B\'s about 16 KB. A difference in validity cannot be attributed to typed ports alone.',
        'Gold provenance: expected.json is hand-authored by the benchmark author; feasibility, coverage and reason keywords are labels, not an independent expert judgment. Acceptance machine-checkability is a lexical proxy.',
        'The 1x1 run has one task and one repetition: validity 1.0 vs 1.0 carries no power, stability is null, and infeasible handling is null. A claim over 12 tasks needs the full run.',
        'The frozen library snapshot (manifest.json) uses deterministic synthetic hashes; "installed capsule" availability in a live deployment is not shown.',
        'Tokens: only the single total printed by codex per call (tokens used), not input/output split. The prompt size is in bytes.',
        ran_gap('Start and end timestamps and the product commit are not recorded by the harness; the codex binary version and the account/profile are not recorded either. The command line is (it names the codex path and an empty temp dir).',
                'The account/profile behind the codex login is not recorded; the codex path and version are in run.json (codex) when the run went through ai4r-bench.'),
        'codex runs "read-only" and "ephemeral" but is only tool-free-ish: nothing proves the model used no tools or read no repo file (planner/README.md).',
        'Order effects: repeats alternate A/B then B/A, but the order actually run is not stored per case beyond file times.']
    intro = ('Plan-only benchmark. ours = arm A (declared capsule library, pinned plan schema); theirs = arm B (plain skill list). Scored by the independent plan_integrity checker against hand-authored labels. '
             'One folder per model x task x repetition; each holds both arms.')
    return finish_bench(out, 'planner', cases, claims, gaps, intro, ('ours (A declared)', 'theirs (B undeclared)'))


def planner_claims(model, scored, folders):
    defects = list(next(iter(scored['aggregate'].values()))['defects_per_plan'])
    mine = planner_aggregate(scored['plans'], defects)
    out = []
    for cond, arm in (('A', 'ours'), ('B', 'theirs')):
        head, rec = scored['aggregate'][cond], mine[cond]
        group = [p for p in scored['plans'] if p['condition'] == cond]
        valid = [folders.get((p['task'], p['repeat'])) for p in group if p['score']['valid']]
        allc = [folders.get((p['task'], p['repeat'])) for p in group]
        rej = [folders.get((p['task'], p['repeat'])) for p in group if not p['expected_feasible']]
        for key in ('plans', 'validity_rate', 'infeasible_handling_accuracy', 'overall_feasibility_decision_accuracy',
                    'acceptance_machine_checkable_fraction', 'run_to_run_stability'):
            num, den = {'validity_rate': (valid, allc), 'infeasible_handling_accuracy': ([f for f, p in zip(allc, group) if (not p['expected_feasible']) and p['score']['infeasible_handling_correct']], rej),
                        'overall_feasibility_decision_accuracy': ([f for f, p in zip(allc, group) if p['score']['infeasible_handling_correct']], allc)}.get(key, (None, allc))
            out.append(claim('%s.%s.%s' % (model, cond, key), '%s arm %s (%s): %s' % (model, cond, arm, key), head[key], rec[key], 'scores/%s.json aggregate.%s.%s' % (model, cond, key),
                             {'cases': num} if num is not None else {'note': 'ratio of sums; see plan_score.json in each case'}, {'cases': den}))
        for d in defects:
            out.append(claim('%s.%s.defects_per_plan.%s' % (model, cond, d), '%s arm %s: defects per plan, %s' % (model, cond, d), head['defects_per_plan'][d], rec['defects_per_plan'][d],
                             'scores/%s.json aggregate.%s.defects_per_plan' % (model, cond),
                             {'cases': [folders.get((p['task'], p['repeat'])) for p in group if p['score']['counts'][d]]}, {'cases': allc}))
    return out


# ---------------------------------------------------------------- nativeadmit

NA = HERE / 'nativeadmit'
NA_CLASS = {'correct': 'correct_delivered', 'correct_flagged': 'correct_delivered', 'justified_halt': 'correct_stop', 'wrong_halt': 'wrong_stop', 'flagged_wrong': 'wrong_delivered',
            'silent_wrong': 'wrong_delivered', 'unavailable': 'unavailable'}


def nonzero(counts):
    """Class counts without zero entries, so headlines written before a class existed still compare."""
    return {k: v for k, v in counts.items() if v}


def na_common_class(bench_class, defective):
    if bench_class == 'wrong_halt' and not defective:
        return 'false_reject'
    return NA_CLASS[bench_class]


def load_na_score():
    spec = importlib.util.spec_from_file_location('ccbench_nativeadmit_score', NA / 'score.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_sessions(R, item, extra):
    bases = ([Path(extra)] if extra else []) + [R / 'sessions', R / 'nativetask' / 'sessions']
    found = []
    for b in bases:
        if b.is_dir():
            found += sorted(p for p in list(b.glob('nadm-%s-*' % item)) + list(b.glob('%s-r[0-9]*' % item)) if p.is_dir())
    mp = R / 'map.json'
    if mp.exists() and item in load(mp):
        found.append(Path(load(mp)[item]))
    seen, out = set(), []
    for p in found:
        if str(p) not in seen:
            seen.add(str(p))
            out.append(p)
    return out


def rep_label(name):
    """nadm-<item>-NN becomes rNN and <item>-rN stays rN; any other name is kept."""
    m = re.search(r'-(r?\d+)$', name)
    return m.group(1) if m and m.group(1)[0] == 'r' else ('r' + m.group(1) if m else name)


def build_nativeadmit(run, out, args):
    R = Path(run)
    sc = load_na_score()
    cc_dir = R / 'cc'
    items = sorted(p.stem for p in (NA / 'referee').glob('*.json') if (cc_dir / (p.stem + '.json')).exists())
    if not items:
        raise SystemExit('no cc/<item>.json under %s (run cc_route.py --out first)' % run)
    decls = load(ADM / 'declarations.json')
    cases = []
    cc_rows, native_rows = [], []
    case_of = {}
    for item in items:
        ref = sc.load_ref(item)
        job = load(NA / 'items' / item / 'job.json')
        sessions = native_sessions(R, item, args.native)
        reps = [(rep_label(s.name), s) for s in sessions] or [('', None)]
        cc_score = sc.score_cc(item, cc_dir)
        cc_json = load(cc_dir / (item + '.json'))
        cc_class = na_common_class(cc_score['class'], ref['defective'])
        first_folder = '%s-%s' % (item, reps[0][0]) if reps[0][0] else item
        for rep, session in reps:
            case = Case(out, '%s-%s' % (item, rep) if rep else item)
            pub = NA / 'items' / item / 'public'
            for f in sorted(pub.iterdir()):
                case.input.copy(f, 'public/' + f.name)
            case.input.copy(NA / 'items' / item / 'job.json', 'ours_job.json')
            case.input.json('declaration_%s.json' % job['tool'], decls[job['tool']])
            if session and (session / 'native/spec.json').exists():
                case.input.copy(session / 'native/spec.json', 'native_spec.json')
                case.input.copy(session / 'staging-receipt.json', 'staging-receipt.json')
            case.input.put('ARMS.md', '\n'.join([
                '# What each arm was given', '',
                '- theirs (native JiuwenSwarm): task text and files in public/ only (task.txt is the prompt; native_spec.json shows the spec actually sent when a session exists). It can read and run the tool. It is not told to test anything.',
                '- ours (CC route, offline): the same tool and data in public/, plus the rich declaration (declaration_%s.json) and how to invoke the tool (ours_job.json). It derives tests with admission/derive.py and admits only if all pass.' % job['tool'],
                '- Gold (oracle/) was given to neither arm.', '']))
            case.ours.copy(cc_dir / (item + '.json'), 'cc_route.json')
            case.ours.put('delivered_or_halt.md', '# CC route result\n\n- admitted: %s\n- tests run: %s, failed: %s\n- delivered answer: %s\n- halt reason: %s\n' % (
                cc_json['admitted'], cc_json['tests_run'], cc_json['failed_tests'], cc_json['delivered_answer'], cc_json['halt_reason']))
            case.oracle.copy(NA / 'referee' / (item + '.json'), 'referee.json')
            case.oracle.put('HOW.md', '\n'.join([
                '# How the gold was made', '',
                '- `referee.json`: gold answer, defect label, ground-truth witness and oracle status, written by `nativeadmit/build_items.py` (copied from nativeadmit/referee/%s.json, never shown to an arm).' % item,
                '- The gold number is `admission/oracle.py:expected` (Fraction arithmetic, independent of every candidate implementation). For calc_comma the oracle rejects "1,250", so gold is the intended sum with comma as thousands separator; for table_pad the oracle rejects the ragged file, so no number is gold and any delivered number is wrong.',
                '- build_items.py asserts that the defect changes the answer on each item\'s data and that both control tools produce the gold; equivalence.json shows the public run() equals the admission candidate on all derived tests.',
                '- Independence from both arms: cc_route.py reads only the declaration and the tool, never gold or labels (README). The native arm never sees referee/.',
                '- Not independent of the author: the same author wrote the declarations, the defects, the data and the gold (README fairness notes).', '']))
            score = {'item': item, 'defective': ref['defective'], 'defect': ref['defect'], 'gold': ref['answer'],
                     'ours': arm_score('CC route', 'admitted' if cc_json['admitted'] else 'halted', cc_class, 'benchmarks/ccbench/nativeadmit/score.py:score_cc',
                                       bench_class=cc_score['class'], delivered=cc_score['delivered']),
                     'class_map': 'correct=correct_delivered, justified_halt=correct_stop, wrong_halt=wrong_stop (false_reject on a control), flagged_wrong and silent_wrong=wrong_delivered'}
            run_json = run_record(model=NA_MODEL, tokens='not applicable (no model call)', ours_route={'command': NR, 'note': 'cc_route.py ran offline; the run folder does not store its command line or time'})
            if session:
                ns = sc.score_native(item, session)
                ncls = na_common_class(ns['class'], ref['defective'])
                native_rows.append((case.name, ns['class'], ncls, ref['defective']))
                for name in ('final-message.txt', 'final-messages.json', 'usage.json', 'collection.json', 'plan.json', 'process-outcome.json',
                             'result.json', 'controller-start.json', 'controller-finished.json', 'controller-timeout.json', 'stderr.log', 'events.jsonl'):
                    case.theirs.copy(session / name, name) if (session / name).exists() else None
                proj = session / 'project'
                if proj.is_dir():
                    case.theirs.json('project_files.json', tree_listing(proj))
                    for f in sorted(proj.iterdir()):
                        if f.is_file() and f.stat().st_size <= LIMIT:
                            case.theirs.copy(f, 'project/' + f.name)
                att = first_existing(session.parent.parent / 'attempts' / (session.name + '.json'), R / 'attempts' / (session.name + '.json'))
                att_product = None
                if att:
                    case.theirs.copy(att, 'attempt_record.json')
                    product = load(att).get('product')
                    if isinstance(product, dict) and product.get('commit'):
                        att_product = product['commit'] + (' (working tree dirty)' if product.get('dirty') else '')
                score['theirs'] = arm_score('native JiuwenSwarm', ns['class'], ncls, 'benchmarks/ccbench/nativeadmit/score.py:score_native (classify_text)',
                                            bench_class=ns['class'], delivered=ns.get('delivered'), flagged_tool=ns.get('flagged_tool'), tool_file_modified=ns.get('tool_file_modified'))
                plan = load(session / 'plan.json') if (session / 'plan.json').exists() else {}
                stage = load(session / 'staging-receipt.json') if (session / 'staging-receipt.json').exists() else {}
                usage = load(session / 'usage.json') if (session / 'usage.json').exists() else None
                tok = NR
                if usage:
                    tin = sum((u.get('usage') or {}).get('input_tokens') or 0 for u in usage)
                    tout = sum((u.get('usage') or {}).get('output_tokens') or 0 for u in usage)
                    tok = {'input_tokens': tin, 'output_tokens': tout, 'source': 'usage.json'}
                start = load(session / 'controller-start.json') if (session / 'controller-start.json').exists() else {}
                fin = load(session / 'controller-finished.json') if (session / 'controller-finished.json').exists() else {}
                run_json.update(model=(plan.get('spec') or {}).get('model', NR), image=stage.get('image', NR), command=plan.get('worker', NR),
                                started_at=start.get('started_at', NR), finished_at=fin.get('finished_at', NR), wall_time_s=fin.get('elapsed_s', NR), tokens=tok,
                                broker_command=plan.get('broker', NR), session=str(session), product_commit=att_product or NR)
                they = 'Native JiuwenSwarm session %s. Class %s (delivered %s, tool doubted: %s).' % (session.name, ns['class'], ns.get('delivered'), ns.get('flagged_tool'))
                verdict = 'CC: %s. Native: %s.' % (cc_score['class'], ns['class'])
                tcls = ncls
            else:
                case.theirs.put('MISSING.md', '\n'.join([
                    '# No native JiuwenSwarm run for this item', '',
                    'The run folder has no session for `%s` (looked in sessions/nadm-%s-*, sessions/%s-r*, nativetask/sessions/, map.json and --native).' % (item, item, item),
                    'The opponent\'s answer, transcript, tokens and image are therefore unavailable. Nothing was invented.', '',
                    'To produce it (operator only; model and Docker):', '',
                    '    sh scripts/ai4r-bench nativetask run --task-file benchmarks/ccbench/nativeadmit/items/%s/public/task.txt --inputs-dir benchmarks/ccbench/nativeadmit/items/%s/public --ledger OUT/ledger.sqlite3 --attempt-id nadm-%s-01 --execute --out OUT' % (item, item, item),
                    '', 'then rerun the dossier with --run OUT (or --native OUT/sessions).', '']))
                score['theirs'] = arm_score('native JiuwenSwarm', 'missing', 'missing', 'benchmarks/ccbench/nativeadmit/score.py:score_native (no session)')
                they = 'No native run available. See theirs/MISSING.md.'
                verdict = 'CC: %s. Native: missing.' % cc_score['class']
                tcls = 'missing'
            asked = 'Use the supplied team tool to compute an answer from the supplied data (task text in input/public/task.txt). Tool defect planted: %s.' % ref['defect']
            we = 'CC route: derived %s tests from the declaration; admitted: %s. %s' % (cc_json['tests_run'], cc_json['admitted'], cc_json['halt_reason'] or 'Delivered %s.' % cc_json['delivered_answer'])
            case.finish('nativeadmit %s%s' % (item, (' ' + rep) if rep else ''), asked, we[:900], they,
                        'Gold answer %s (defect: %s). Provenance in oracle/HOW.md.' % (ref['answer'], ref['defect']), verdict, score, run_json)
            cases.append({'folder': case.name, 'ours': cc_class, 'theirs': tcls})
            case_of[case.name] = item
        cc_rows.append((first_folder, cc_score['class'], cc_class))
    claims = na_claims(R, sc, cc_rows, native_rows)
    gaps = [
        'Opponent output: ' + ('present for %d case(s) from the native sessions found.' % len(native_rows) if native_rows else
                                'NO native run exists in this run folder; every case has theirs/MISSING.md. Nothing can be said about what the opponent answered, how many tokens it used or whether it noticed the defect.'),
        'The CC arm is offline pre-registered logic, not a model run: it has no transcript or tokens by design. ' + ('Its cc_route.py command is in run.json run_meta when it ran through ai4r-bench into this folder.' if META else '"How exactly it was run" is the cc_route.py command, which the run folder does not store.'),
        'The CC route halted on %d of %d items (%d defective). The README says 5 of the defective items still have a gold number a native agent can reach by hand; a halt counts as a win for CC even where no number is delivered (caveat on SCORING-RULES 3.3). Read the CC class next to coverage on the %d controls.'
        % (sum(1 for _, bc, _ in cc_rows if bc == 'justified_halt'), len(cc_rows), sum(1 for i in items if sc.load_ref(i)['defective']), sum(1 for i in items if not sc.load_ref(i)['defective'])),
        'Gold provenance: oracle.expected is independent of the candidates, but the author of the data, defects, declarations and gold is the same; no external review.',
        'Native scoring is a text heuristic (score.py:classify_text: first Answer/bold number, tool-doubt regexes). A reviewer should open theirs/final-message.txt to confirm the extracted number and the doubt flag. No AI judge is used.',
        'Tokens, image digest: recorded only if a native session with usage.json and staging-receipt.json is present; the CC arm has none. Product commit: %s' % (
            'from the attempt record where nativetask wrote it, else from the run-meta of the whole run (run.json run_meta).' if META else 'nativetask does not record it and this run has no run-meta, so run.json says "not recorded".'),
        'Item data are small synthetic files; one run per item, so no confidence statement beyond the item table (README).',
        'Defect visibility: several defects are visible by reading the tool source, so a native win there is legitimate and proves nothing about CC.']
    intro = ('Tool admission against a real user job. ours = CC route (declaration-derived admission tests, offline); theirs = native JiuwenSwarm with ordinary tools (missing unless sessions are in the run folder). '
             'Common classes; the bench\'s own class names are in score.json (bench_class).')
    return finish_bench(out, 'nativeadmit', cases, claims, gaps, intro, ('ours (CC route)', 'theirs (native)'))


def na_claims(R, sc, cc_rows, native_rows):
    out = []
    head_cc = None
    for cand in sorted(R.glob('*score-cc*')):
        try:
            head_cc = load(cand)['metrics']
            src = cand.name
            break
        except (ValueError, KeyError):
            continue
    mine = sc.metrics([c for _, c, _ in cc_rows])
    groups = {}
    for folder, bc, _ in cc_rows:
        groups.setdefault(bc, []).append(folder)
    for cls in sc.CLASSES:
        out.append(claim('CC.count.' + cls, 'CC route: items classed %s' % cls, head_cc['counts'].get(cls, 0) if head_cc else None, mine['counts'][cls],
                         src if head_cc else 'no score-cc json in the run folder', {'cases': groups.get(cls, [])}, {'cases': [f for f, _, _ in cc_rows]},
                         '' if head_cc else 'no headline: run score.py cc --out to write score-cc.json'))
    for key in ('delivered_precision', 'silent_wrong_rate', 'utility'):
        out.append(claim('CC.' + key, 'CC route: ' + key, head_cc[key] if head_cc else None, mine[key], src if head_cc else 'no score-cc json in the run folder',
                         {}, {'cases': [f for f, _, _ in cc_rows]}, '' if head_cc else 'no headline: run score.py cc --out to write score-cc.json'))
    if native_rows:
        head_n = None
        summ = R / 'score-summary.json'
        if summ.exists():
            head_n = load(summ).get('native', {}).get('metrics')
        # score-summary.json scores one session per item (its --map). With several reps per item the headline covers
        # one rep: use the rep subset whose size matches the headline and say so; otherwise there is no comparable headline.
        head_rows = len((load(summ).get('native') or {}).get('rows', [])) if summ.exists() else 0
        subset, note = native_rows, ''
        if head_n and head_rows != len(native_rows):
            by_rep = {}
            for row in native_rows:
                by_rep.setdefault(row[0].rsplit('-', 1)[-1], []).append(row)
            same = [r for r, rows in sorted(by_rep.items()) if len(rows) == head_rows and nonzero(sc.metrics([c for _, c, _, _ in rows])['counts']) == nonzero(head_n['counts'])]
            if same:
                subset, note = by_rep[same[0]], 'score-summary.json covers %d sessions; the %d sessions of rep %s reproduce it' % (head_rows, head_rows, same[0])
            else:
                head_n, note = None, 'no headline: score-summary.json covers %d sessions but the dossier holds %d and no single rep reproduces it' % (head_rows, len(native_rows))
        nm = sc.metrics([c for _, c, _, _ in subset])
        ng = {}
        for folder, bc, _, _ in subset:
            ng.setdefault(bc, []).append(folder)
        src = 'score-summary.json' if head_n else 'no comparable score-summary.json in the run folder'
        none_note = note or 'no headline: run score.py summary --map to write score-summary.json'
        for cls in sc.CLASSES:
            out.append(claim('native.count.' + cls, 'native: items classed %s' % cls, head_n['counts'].get(cls, 0) if head_n else None, nm['counts'][cls],
                             src, {'cases': ng.get(cls, [])}, {'cases': [f for f, _, _, _ in subset]}, note if head_n else none_note))
        for key in ('delivered_precision', 'silent_wrong_rate', 'utility'):
            out.append(claim('native.' + key, 'native: ' + key, head_n[key] if head_n else None, nm[key], src,
                             {}, {'cases': [f for f, _, _, _ in subset]}, note if head_n else none_note))
        if len(subset) != len(native_rows):
            allm = sc.metrics([c for _, c, _, _ in native_rows])
            out.append(claim('native.all_sessions.counts', 'native: class counts over all %d sessions (no harness headline)' % len(native_rows), None, allm['counts'],
                             'recomputed from every native session', {}, {'cases': [f for f, _, _, _ in native_rows]}, 'no headline: the harness summary does not cover every rep'))
    return out


# ---------------------------------------------------------------- planbench

PB = HERE / 'planbench'
PB_WEIGHTS = {'correct': 1, 'justified_halt': 1, 'wrong_halt': 0, 'flagged_wrong': -1, 'silent_wrong': -3}
PB_RULE = 'benchmarks/ccbench/planbench/score.py:score_item (classify, SCORING-RULES 3.1)'


def pb_common_class(cls, feasible):
    if cls == 'wrong_halt':
        return 'false_reject' if feasible else 'wrong_stop'
    return {'correct': 'correct_delivered', 'justified_halt': 'correct_stop', 'flagged_wrong': 'wrong_delivered', 'silent_wrong': 'wrong_delivered'}.get(cls, cls)


def pb_copy_tree(part, src, prefix):
    src = Path(src)
    if src.is_dir():
        for f in sorted(src.rglob('*')):
            if f.is_file():
                part.copy(f, prefix + f.relative_to(src).as_posix())


def build_planbench(run, out, args):
    R = Path(run)
    labels = sorted(d.name for d in (R / 'runs').iterdir() if d.is_dir()) if (R / 'runs').is_dir() else []
    if not labels:
        raise SystemExit('no runs/<label>/ under %s (planbench run --label LABEL --out DIR writes them)' % run)
    tasks = {t['id']: t for t in load(PB / 'tasks.json')}
    gold = load(PB / 'referee' / 'gold.json')
    cases, claims, scored_labels, stub_cases, native_arm = [], [], [], [], []
    for label in labels:
        base = R / 'runs' / label
        sp = R / 'scores' / (label + '.json')
        scored = load(sp) if sp.exists() else None
        items = {(i['arm'], i['task']): i for i in (scored['items'] if scored else [])}
        task_ids = sorted({d.name for arm in ('cc', 'skill') if (base / arm).is_dir() for d in (base / arm).iterdir() if d.is_dir()})
        classes = {'cc': {}, 'cc_ungated': {}, 'skill': {}}
        for tid in task_ids:
            task, g = tasks[tid], gold[tid]
            case = Case(out, '%s__%s' % (label, tid))
            recs = {}
            for arm in ('cc', 'skill'):
                d = base / arm / tid
                recs[arm] = (d, load(d / 'record.json')) if (d / 'record.json').exists() else (d, None)
            case.input.json('task.json', task)
            for arm, part, name in (('cc', case.ours, 'ours'), ('skill', case.theirs, 'theirs')):
                d, rec = recs[arm]
                part_in = 'request_%s.txt' % name
                if (d / 'request.txt').exists():
                    case.input.copy(d / 'request.txt', part_in)
                if (d / 'prompt.txt').exists():
                    case.input.copy(d / 'prompt.txt', 'prompt_%s.txt' % name)
            case.input.copy(PB / 'SHA256SUMS', 'frozen_inputs_SHA256SUMS')
            case.input.put('ARMS.md', '\n'.join([
                '# What each arm was given', '',
                '- ours (CC arm): request_ours.txt as the Brief objective, plus the library snapshot of the 18 selectable capsules with declared ports, pins, check ids and plan policy (planner/library.py, hashes in record via the cclib store). The real research.planner worker, planner_checks, semantic verifier and gate then ran.',
                '- theirs (skill arm): request_theirs.txt (the same request plus a neutral JSON answer format) and the same 18 capabilities as plain tool files and skill folders (planbench/skillpack, hashes in frozen_inputs_SHA256SUMS): name, one-line summary, how to call. Nothing checked the plan after the model.',
                '- Both plans are parsed into one neutral form (normalize.py), executed by one executor (executor.py) and compared with the referee. Gold (oracle/) was given to neither arm.', '']))
            views = {}
            for arm, part, name, vlist in (('cc', case.ours, 'ours', ('cc', 'cc_ungated')), ('skill', case.theirs, 'theirs', ('skill',))):
                d, rec = recs[arm]
                if rec is None:
                    part.put('MISSING.md', '# No %s arm for this task in label %s\n\nThe run folder has no runs/%s/%s/%s/record.json. Nothing was invented.\n' % (arm, label, label, arm, tid))
                    continue
                for f in ('record.json', 'reply.txt', 'native.stdout', 'native.stderr'):
                    part.copy(d / f, f)
                pb_copy_tree(part, d / 'codex', 'codex/')
                sess = rec.get('session')
                if sess and Path(sess).is_dir():
                    for f in ('final-message.txt', 'usage.json', 'plan.json', 'staging-receipt.json', 'controller-start.json', 'controller-finished.json', 'result.json', 'stderr.log'):
                        part.copy(Path(sess) / f, 'session/' + f)
                it = items.get((arm, tid))
                for v in vlist:
                    cls = it['views'][v]['class'] if it and v in it['views'] else 'unscored'
                    classes[v][tid] = cls
                    views[v] = (cls, it['views'][v]['detail'] if it and v in it['views'] else '')
                if rec.get('stub'):
                    stub_cases.append(case.name)
                if arm == 'skill' and rec.get('session'):
                    native_arm.append(case.name)
            case.oracle.json('gold.json', g)
            case.oracle.copy(PB / 'referee' / 'oracle.py', 'oracle.py')
            case.oracle.put('HOW.md', '\n'.join([
                '# How the gold was made', '',
                '- `gold.json` (planbench/referee/gold.json, generated by generate_tasks.py): feasibility, the expected deliverables with their locators and values, decoys, the reference plan and the reason regex for infeasible tasks. Neither arm saw it.',
                '- Correctness is measured by running each plan through executor.py over the task inputs and comparing the deliverables with `expected`; the model\'s own claim about its plan is not believed (README).',
                '- Not independent of the author: tasks, capabilities, gold and executor were written by one author; the reason regexes for infeasible tasks are keyword labels.', '']))
            score = {'task': tid, 'feasible': g['feasible'], 'label': label, 'class_rule': 'planbench classes mapped to common classes: correct=correct_delivered, justified_halt=correct_stop, wrong_halt=false_reject on a feasible task and wrong_stop on an infeasible one, flagged_wrong and silent_wrong=wrong_delivered'}
            for key, v, arm_name in (('ours', 'cc', 'CC arm (gated, as shipped)'), ('theirs', 'skill', 'skill arm')):
                if v in views:
                    cls, detail = views[v]
                    score[key] = arm_score(arm_name, cls + (' (%s)' % detail if detail else ''), pb_common_class(cls, g['feasible']), PB_RULE, bench_class=cls)
                else:
                    score[key] = arm_score(arm_name, 'missing', 'missing', PB_RULE + ' (no record)')
            if 'cc_ungated' in views:
                score['ours']['ungated_view'] = {'bench_class': views['cc_ungated'][0], 'class': pb_common_class(views['cc_ungated'][0], g['feasible'])}
            r_cc, r_sk = recs['cc'][1] or {}, recs['skill'][1] or {}
            models = sorted({r.get('model') for r in (r_cc, r_sk) if r.get('model')})
            run_json = run_record(model=models[0] if len(models) == 1 else (models or NR), label=label,
                                  stub=[r.get('stub') for r in (r_cc, r_sk) if r],
                                  arms={a: {k: r.get(k) for k in ('label', 'status', 'delivered', 'model_calls', 'tokens', 'elapsed_s', 'effort', 'stub', 'returncode', 'session') if k in r}
                                        for a, r in (('ours_cc', r_cc), ('theirs_skill', r_sk)) if r},
                                  tokens={a: r.get('tokens') for a, r in (('ours_cc', r_cc), ('theirs_skill', r_sk)) if r} or NR,
                                  note='per-arm status, tokens and elapsed time are under arms; the command line and start/end times are in run_meta when the run went through ai4r-bench')
            ours_c = score['ours']['class']
            theirs_c = score['theirs']['class']
            case.finish('planbench %s (run %s)' % (tid, label),
                        'Plan the job `%s` (%s; expected feasible: %s) from the supplied capabilities. Task text in input/task.json.' % (tid, task.get('category', ''), g['feasible']),
                        'CC arm: %s. See ours/reply.txt and ours/record.json.' % (score['ours']['verdict']),
                        'Skill arm: %s. See theirs/reply.txt and theirs/record.json.' % (score['theirs']['verdict']),
                        'Feasible: %s. Expected deliverables: %s. Provenance: oracle/HOW.md.' % (g['feasible'], ', '.join(d['id'] for d in g['deliverables']) or 'none (must be declared infeasible)'),
                        'CC: %s. Skill: %s.' % (ours_c, theirs_c), score, run_json)
            cases.append({'folder': case.name, 'ours': ours_c, 'theirs': theirs_c})
        claims += pb_claims(label, scored, classes)
        scored_labels.append((label, bool(scored)))
    gaps = [
        'Opponent output: the skill arm is the same model with plain tool files and skill folders; its transport is %s. Its reply is the whole artifact; nothing is checked after it. The CC arm sees full typed declarations and the skill arm only names and summaries, so a difference cannot be attributed to the checks alone (README design).'
        % ('native JiuwenSwarm (session folders in theirs/session)' if native_arm else 'the single tool-free codex exec turn (labelled fallback), not native JiuwenSwarm'),
        'Stub rows: %s. A stub case is a scripted reply, not a model run; its class says nothing about a model.' % (', '.join(stub_cases) if stub_cases else 'none (every case record has stub null)'),
        'Gold provenance: tasks, capability set, gold deliverables, executor and reason regexes come from one author (README). Infeasible tasks are matched by a keyword regex on the stated reason.',
        'Scoring: %s' % ('; '.join('%s: %s' % (l, 'scores/%s.json present' % l if s else 'no scores/%s.json (cases are unscored)' % l) for l, s in scored_labels)),
        'Sample size: 12 tasks, one run per task and arm per label. A class count is a count of single runs, not a rate with an interval.',
        ran_gap('How exactly it was run: no command line, product commit, codex version, image digest, start or end time is stored by the harness (run.json: not recorded; per-arm elapsed time and tokens are).',
                'How exactly it was run: the account/profile behind the codex login is not recorded; per-arm elapsed time and tokens are in run.json arms.'),
        'Tokens: the single total codex printed per call (tokens used), or the native broker usage; not split into input and output on the CC arm.',
        'The skillpack was generated with older product summaries (README "Known stale input"); the skill arm sees those, not the current table_packet wording.',
        'The CC arm needs the pinned openjiuwen runtime; a record with reasons "native_unavailable" is a harness failure scored wrong_halt, not a planning result. Check ours/record.json reasons.']
    intro = ('Plan quality, executed. ours = CC arm (real planner worker + checks + gate; gated view, the ungated view is in score.json); theirs = skill arm (plain tools and skills). '
             'One folder per (run label, task). Common classes; the bench class names are in score.json (bench_class).')
    return finish_bench(out, 'planbench', cases, claims, gaps, intro, ('ours (CC arm)', 'theirs (skill arm)'))


def pb_claims(label, scored, classes):
    out = []
    names = ('correct', 'justified_halt', 'wrong_halt', 'flagged_wrong', 'silent_wrong', 'unavailable')
    for view, per_task in classes.items():
        if not per_task:
            continue
        counts = {c: sum(1 for x in per_task.values() if x == c) for c in names}
        delivered = counts['correct'] + counts['flagged_wrong'] + counts['silent_wrong']
        avail = len(per_task) - counts['unavailable']
        mine = {'counts': counts, 'delivered_precision': counts['correct'] / delivered if delivered else None,
                'utility': sum(PB_WEIGHTS.get(x, 0) * n for x, n in counts.items()) / avail if avail else None}
        head = ((scored or {}).get('summary') or {}).get(view)
        note = '' if head else 'no headline: run planbench score --label %s to write scores/%s.json' % (label, label)
        src = 'scores/%s.json summary.%s' % (label, view) if head else 'no scores/%s.json' % label
        cases = {'cases': sorted(per_task)}
        for cls in names:
            out.append(claim('%s.%s.count.%s' % (label, view, cls), '%s %s: tasks classed %s' % (label, view, cls), head['classes'][cls] if head else None, counts[cls],
                             src, {'tasks': sorted(t for t, x in per_task.items() if x == cls)}, cases, note))
        out.append(claim('%s.%s.delivered_precision' % (label, view), '%s %s: delivered precision' % (label, view),
                         head['delivered_precision']['value'] if head else None, mine['delivered_precision'], src, {}, cases, note))
        out.append(claim('%s.%s.utility' % (label, view), '%s %s: utility' % (label, view), head['utility'] if head else None, mine['utility'], src, {}, cases, note))
    return out


# ---------------------------------------------------------------- entry

BUILDERS = {'admission': build_admission, 'gatebench': build_gatebench, 'trapcheck': build_trapcheck, 'planner': build_planner,
            'nativeadmit': build_nativeadmit, 'planbench': build_planbench}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('bench', choices=list(BENCHES), help='bench whose run output to read')
    parser.add_argument('--run', type=Path, required=True, help='the bench\'s run output directory (read only)')
    parser.add_argument('--out', type=Path, required=True, help='directory the dossier is written to')
    parser.add_argument('--data', type=Path, help='trapcheck: evidence root that holds traps/ (default: AI4R_BENCH_DATA)')
    parser.add_argument('--native', type=Path, help='nativeadmit: folder holding nadm-<item>-NN native sessions (default: RUN/sessions)')
    parser.add_argument('--meta', action='append', default=[], metavar='KEY=VALUE', help='operator-supplied run facts, recorded in INDEX.md (repeatable)')
    args = parser.parse_args(argv)
    run = args.run.resolve()
    out = args.out.resolve()
    if not run.is_dir():
        raise SystemExit('--run %s is not a directory' % run)
    if run == out or run in out.parents or out in run.parents:
        raise SystemExit('--out must be a different folder, not inside or around --run (the dossier never writes into the run)')
    out.mkdir(parents=True, exist_ok=True)
    META[:] = load_meta(run)
    cases, claims, bad = BUILDERS[args.bench](run, out, args)
    if args.meta:
        put_json(out / 'operator_meta.json', dict(m.split('=', 1) for m in args.meta if '=' in m))
    print('%s: %d cases, %d headline numbers recomputed, %d mismatched -> %s' % (args.bench, cases, claims, bad, out))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
