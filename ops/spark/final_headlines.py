"""Build the demo headline table from the admitted reference, mirror and pooled results."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

SIZES = (512, 2048)


def pair(values, unit, signed=False):
    spec = '+.2f' if signed else '.2f'
    return ' / '.join(format(value, spec).replace('-', '−') for value in values) + ' ' + unit


def build(root, allow_pending=False):
    rows = []
    path = root / 'OPS/iterations'

    def add(key, arm, cc, grade, ttft, decode, summary, refs):
        sources = []
        for source in refs:
            data = source.read_bytes()
            sources.append(dict(path=source.relative_to(root).as_posix(), sha256=hashlib.sha256(data).hexdigest()))
        rows.append(dict(id=key, arm=arm, cc=cc, grade=grade, ttft=ttft, decode=decode, summary=summary, sources=sources))

    reference = path / 'spark-a-s-cold-steady/reference'
    cache_reference = path / 'spark-c3-native-cache/full'
    for key, arm, folder, source_arm, text in (
        ('s', 'Strata (S)', reference, 'S-fair-steady', 'Fair Strata decoded about 17 tokens per second on both prompts.'),
        ('a', 'Stock CPU experts (A-matched)', reference, 'A-matched-speed-30720MiB', 'CPU experts returned the first token quickly, then generated about three tokens per second.'),
        ('aplus', 'Stock native cache (A+30)', cache_reference, 'Aplus-speed-30720MiB', 'Stock A+30 beat Strata on both observed medians. The 2048-token decode margin was just 0.16 tok/s.'),
    ):
        analysis = json.loads((folder / 'analysis.json').read_bytes())
        samples = next(s['samples'] for s in analysis['scopes'] if s['arm'] == source_arm)
        def reference_medians(metric):
            return [median(r[metric] for r in samples if not r['discard'] and r['prompt_tokens'] == size) for size in SIZES]
        add(key, arm, None, 'Screening · reference', pair(reference_medians('ttft_s'), 's'),
            pair(reference_medians('decode_tps'), 'tok/s'), text, [folder/'report.md'])

    for key, arm, name, filename, projection, grade, text in (
        ('c3-original30', 'C3 seeded cache · 30 GiB', 'spark-p4-cache30-attribution', 'iteration.json', 'focused_comparison',
         'Verified · quiet ABBA', 'The early improvement disappeared. Seeding added latency at 2048 tokens and gave no clear decode gain.'),
        ('c3-direct30', 'C3 direct seed · 30 GiB', 'spark-p4-cache30-direct-seed', 'iteration-v2.json', 'focused_comparison',
         'Verified · quiet ABBA', 'Warm results were close to stock. At 512 tokens, cold-request savings were 15.83 and 12.06 s after ready; including startup saved 11.97 and 1.06 s.'),
        ('c3-60', 'C3 seeded cache · 60 GiB', 'spark-p4-cache60-build-overlap', 'iteration-v2.json', 'screening_comparison',
         'Screening · build overlap', 'C3 saved time in 10/10 pairs per size. The six quiet pairs saved 26.80 / 100.23 s; the engine recorded fewer storage reads before the first token.'),
    ):
        folder = path/name
        envelope = json.loads((folder/filename).read_bytes())
        cells = sorted(envelope['analysis'][projection]['rows'], key=lambda c: c['prompt_tokens'])
        assert [(c['prompt_tokens'], c['n']) for c in cells] == [(size, 10) for size in SIZES]
        report = folder / Path(envelope['report']['artifact_id']).name
        assert hashlib.sha256(report.read_bytes()).hexdigest() == envelope['report']['sha256']
        add(key, arm, 'C3', grade,
            pair([c['paired_ttft_seconds_saved_vs_Aplus']['estimate'] for c in cells], 's saved', True),
            pair([c['paired_decode_tps_gained_vs_Aplus']['estimate'] for c in cells], 'tok/s gained', True), text, [report])

    for cc, arm, text in (
        ('C4', 'C4 demand predictor', 'All 96 completed prefetches went unused. Output matched stock; CPU work overlapped this screen.'),
        ('D', 'D combined build', 'All five gates were requested. Recording and placement ran. The other gates declined the stock settings, and CPU work overlapped this screen.'),
        ('C5', 'C5 mapper + serving settings', None),
        ('C2', 'C2 layer-27 placement', 'The layer-27 package showed faster decode at both sizes. Tensor placement and actual native-bank allocation both changed.'),
    ):
        folder = path/f'spark-pooled30-{cc.lower()}-01'
        if not (folder/'iteration.json').is_file() and allow_pending and cc == 'C5':
            add('c5', arm, cc, 'Awaiting screening', 'Pending', 'Pending', 'The repaired source passed its verifier. Timing will appear after the capped launch.', [root/'OPS/p3/mapper-alora-source-product.json'])
            continue
        envelope = json.loads((folder/'iteration.json').read_bytes())
        result = envelope['analysis']['pooled_comparison']
        report = folder/'report.md'
        assert hashlib.sha256(report.read_bytes()).hexdigest() == envelope['report']['sha256']
        cells = sorted(result['rows'], key=lambda c: c['prompt_tokens'])
        assert result['subject_arm'] == cc and result['control_count'] == 4
        assert [(c['prompt_tokens'], c['n']) for c in cells] == [(size, 4) for size in SIZES]
        if cc == 'C5':
            assert not result['greedy_parity']
            text = 'All six long prompts split at 1536/512. Serving flags and greedy output differed from stock at both sizes; the timing covers the whole package.'
        add(cc.lower(), arm, None if cc == 'D' else cc, 'Screening · pooled A+30',
            pair([c['pooled_estimates']['ttft_seconds_saved']['median'] for c in cells], 's saved', True),
            pair([c['pooled_estimates']['decode_tps_gained']['median'] for c in cells], 'tok/s gained', True),
            text, [report])
        if cc == 'C5' and ((folder/'iteration-v2.json').exists() or not allow_pending):
            revision = json.loads((folder/'iteration-v2.json').read_bytes())
            report = folder/'report-v2.md'
            assert hashlib.sha256(report.read_bytes()).hexdigest() == revision['report']['sha256']
            matched = revision['analysis']['matched_stock_comparison']
            cells = sorted(matched['rows'], key=lambda c: c['prompt_tokens'])
            assert [(c['prompt_tokens'], c['n']) for c in cells] == [(size, 4) for size in SIZES]
            for key, field, name, grade, summary in (
                ('c5-mapper-matched', 'c5_vs_stock_flags', 'C5 mapper at matched settings',
                 'Screening · flags-matched A+30', 'At matched settings, TTFT differences crossed zero at both sizes and stock decoded faster at every measured position.'),
                ('c5-stock-flags', 'stock_flags_vs_pooled', 'Stock A+30 serving settings',
                 'Screening · pooled A+30', 'Changing only the stock serving settings reproduced the apparent package gain.'),
            ):
                parity = [c['greedy_parity'][field] for c in cells]
                if all(parity):
                    summary += ' Greedy output matched at both sizes.'
                elif not any(parity):
                    summary += ' Greedy output differed at both sizes.'
                else:
                    summary += ' Greedy output matched only at ' + str(SIZES[parity.index(True)]) + ' tokens.'
                if matched['cpu_overlap_observed']['stock_flags']:
                    summary += ' CPU work overlapped the matched stock launch.'
                add(key, name, cc, grade,
                    pair([c[field]['ttft_seconds_saved']['median'] for c in cells], 's saved', True),
                    pair([c[field]['decode_tps_gained']['median'] for c in cells], 'tok/s gained', True),
                    summary, [report])
    add('c1', 'C1 event recorder', 'C1', 'Verified · functional', 'Unmeasured', 'Unmeasured',
        'DeepSeek produced all 1,360 expected events. The Granite scorer passed and accounted for one lost event per fixture configuration.',
        [path/'spark-c1-functional/report-v3.md'])
    return dict(schema='spark-final-headlines/1', title='DeepSeek on Spark GB10',
                summary='The build-overlapped 60 GiB screen found earlier first tokens and fewer engine reads with profile seeding. Stock A+30 already beat fair Strata on the observed medians.',
                rows=rows)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, default=Path.home()/'predemo-spark')
    cli.add_argument('--allow-pending', action='store_true')
    args = cli.parse_args()
    result = build(args.root, args.allow_pending)
    out = args.root/'OPS/final-headlines.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
