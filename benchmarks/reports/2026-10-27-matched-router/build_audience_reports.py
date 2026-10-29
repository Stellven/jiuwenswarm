"""Build audience reports from completed measurements only. Never invokes models."""
import ast
import base64
from collections import Counter
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import zipfile

os.environ.setdefault('MPLCONFIGDIR', 'D:/ai4r-cache/matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
OUTPUT = REPO/'benchmarks/output'
PUBLIC = Path('D:/ai4r-cache/reports/matched-v8-public')
SOURCE = json.loads((ROOT/'assessment.json').read_text(encoding='utf-8'))
ARMS = ['chatgpt-ai4r', 'hybrid']
LABELS = ['Fixed ChatGPT in AI4R', 'Hybrid v8']
ROWS = SOURCE['observations']
COHORTS = [SOURCE['arms'][a] for a in ARMS]
VARIANTS = sorted({r['variant'] for r in ROWS})
BLUE, TEAL, RED, GOLD, GREY = '#355ca8', '#087f8c', '#b94d45', '#c38c1e', '#728299'
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11, 'axes.spines.top':False,
    'axes.spines.right':False, 'axes.titleweight':'bold', 'text.color':'#19314e',
    'axes.labelcolor':'#314059', 'figure.facecolor':'white', 'savefig.facecolor':'white'})

# Reuse the previous report's HTML/Markdown renderer and visual system, without
# importing its dataset, running its builder or altering the original reports.
old = ROOT.parent/'2026-10-26-hybrid-router/build_audience_reports.py'
tree = ast.parse(old.read_text(encoding='utf-8').replace('Measurements: 26 Oct 2026', 'Measurements: 27 Oct 2026'))
nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in {'inline', 'Report'}]
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(old), 'exec'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True)+'\n', encoding='utf-8')


def role_total(cohort, role):
    return sum(cohort['roles'].get(role, {}).get(k, 0) for k in ('input_tokens', 'output_tokens'))


def save(fig, folder, name):
    (folder/'figures').mkdir(parents=True, exist_ok=True)
    fig.savefig(folder/'figures'/name, dpi=160, bbox_inches='tight')
    plt.close(fig)


def figures(external, internal):
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), layout='constrained')
    for ax, values, title, ylabel, maximum, suffix in [
        (axes[0], [100*c['worker_correct']/c['observations'] for c in COHORTS],
         'Matched observed worker-answer accuracy', 'Exact-correct answers (%)', 116, '%'),
        (axes[1], [c['total_tokens'] for c in COHORTS], '18.19% fewer reported tokens',
         'Input + output tokens, all roles', 285000, '')]:
        bars = ax.bar(LABELS, values, color=[BLUE, TEAL], width=.56)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x()+bar.get_width()/2, value+maximum*.022,
                f'{value:g}%' if suffix else f'{value:,.0f}', ha='center', weight='bold')
        ax.set(title=title, ylabel=ylabel, ylim=(0, maximum)); ax.grid(axis='y', alpha=.13); ax.set_axisbelow(True)
    fig.text(.01, -.04, 'Eight public development fixtures, three repeats each. Worker correctness is not end-to-end delivery success.', fontsize=9, color=GREY)
    save(fig, external, '01-efficiency-and-accuracy.png')

    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.9), layout='constrained')
    bottom = np.zeros(2)
    for role, label, color in [('worker','Worker',BLUE), ('verifier','Verifier',TEAL), ('routing_selection','Selector',GOLD)]:
        values = np.array([role_total(c, role) for c in COHORTS])
        axes[0].bar(LABELS, values/1000, bottom=bottom/1000, width=.56, color=color, label=label)
        bottom += values
    axes[0].set(title='Both arms include verifier overhead', ylabel='Reported tokens (thousands)', ylim=(0, 290))
    axes[0].legend(frameon=False, ncols=3, fontsize=9, loc='upper left'); axes[0].grid(axis='y', alpha=.13); axes[0].set_axisbelow(True)
    axes[1].barh([0], [18], color=BLUE, label='ChatGPT subscription')
    axes[1].barh([0], [6], left=[18], color=TEAL, label='Local Lightning')
    for center, text in [(9,'18'), (21,'6')]:axes[1].text(center,0,text,ha='center',va='center',color='white',fontsize=23,weight='bold')
    axes[1].set(title='Hybrid v8: actual worker dispatch', xlabel='Worker calls', yticks=[], xlim=(0,24), ylim=(-1,1))
    axes[1].legend(frameon=False, loc='upper left', fontsize=9)
    fig.text(.01,-.04,'Hybrid: 24 workers + 24 verifiers + 6 selectors. Reference: 24 workers + 24 verifiers. Token counts are not dollar costs.',fontsize=9,color=GREY)
    save(fig, external, '02-token-accounting-and-routing.png')

    fig, ax = plt.subplots(figsize=(9, 5.7), layout='constrained')
    values = np.array([[sum(r['correct'] for r in ROWS if r['arm']==a and r['variant']==v) for a in ARMS] for v in VARIANTS])
    ax.imshow(values, cmap='GnBu', vmin=0, vmax=3, aspect='auto')
    for i in range(8):
        for j in range(2):ax.text(j,i,f'{values[i,j]}/3',ha='center',va='center',fontsize=13,color='white',weight='bold')
    ax.set(xticks=[0,1],xticklabels=LABELS,yticks=np.arange(8),yticklabels=VARIANTS,title='Both arms answered all eight fixtures correctly')
    ax.tick_params(length=0,pad=10)
    for spine in ax.spines.values():spine.set_visible(False)
    fig.text(.01,-.03,'c01: all three hybrid attempts used actual GPT-6.1-Sol. Public development cases; not held-out evaluation.',fontsize=9,color=GREY)
    save(fig, external, '03-per-fixture-results.png')

    fig, ax = plt.subplots(figsize=(10.5,4.9),layout='constrained')
    for i,c in enumerate(COHORTS):
        ax.bar(i,c['gated_correct'],color=TEAL,width=.55,label='Correct + advanced' if i==0 else None)
        ax.bar(i,c['false_blocks'],bottom=c['gated_correct'],color=RED,width=.55,label='Correct + blocked' if i==0 else None)
        ax.text(i,10,'20 advanced',ha='center',va='center',color='white',weight='bold',fontsize=15)
        ax.text(i,22,'4 blocked',ha='center',va='center',color='white',weight='bold',fontsize=13)
    ax.set(xticks=[0,1],xticklabels=LABELS,ylim=(0,28),ylabel='Observations out of 24',title='Each arm lost four correct answers at the gate')
    ax.legend(frameon=False,ncols=2,loc='upper left');ax.grid(axis='y',alpha=.13);ax.set_axisbelow(True)
    fig.text(.01,-.04,'All 48 worker answers were correct. Verifier false-block rate: 4/24 = 16.67% in each arm.',fontsize=9,color=GREY)
    save(fig, internal, '01-gate-false-blocks.png')

    fig, ax = plt.subplots(figsize=(9,5.8),layout='constrained')
    matrix=np.array([[sum(r['correct'] and r['gate']!='advance' for r in ROWS if r['arm']==a and r['variant']==v) for a in ARMS] for v in VARIANTS])
    ax.imshow(matrix,cmap='OrRd',vmin=0,vmax=3,aspect='auto')
    for i in range(8):
        for j in range(2):ax.text(j,i,str(matrix[i,j]),ha='center',va='center',fontsize=14,color='white' if matrix[i,j]>=2 else '#19314e')
    ax.set(xticks=[0,1],xticklabels=LABELS,yticks=np.arange(8),yticklabels=VARIANTS,title='Equal totals, different false-block locations')
    ax.tick_params(length=0,pad=10)
    for spine in ax.spines.values():spine.set_visible(False)
    fig.text(.01,-.03,'Cells count correct answers blocked across three repeats. Matching aggregate rates do not imply stable decisions.',fontsize=9,color=GREY)
    save(fig, internal, '02-false-blocks-by-fixture.png')
    shutil.copyfile(external/'figures/02-token-accounting-and-routing.png',internal/'figures/03-full-token-accounting.png')


def common_sections(r, data_name='measurements.json'):
    r.h('Method, scope and evidence')
    r.table(['Property','Recorded method'],[
        ['Assignments','MR01: inference, retrieval, shortest path, performance, database, quorum, reliability and paired data.'],
        ['Sample','Eight public development fixtures, each repeated three times in each arm; 24 observations per arm, not 24 independent tasks.'],
        ['Reference','GPT-6.1-Sol / medium as the fixed worker through AI4R, with the same independent local verifier and structural check as hybrid.'],
        ['Routing','General task-risk guards, then bounded gpt-oss-20b selection among eligible models; no case-ID or answer lookup.'],
        ['Execution','Sequential isolated component observations through the actual production model bridge; no external tools or downloads.'],
        ['Time envelopes','Worker 90 s, including selector time when used; selector at most 30 s / 1,024 output tokens; verifier separately 60 s.'],
        ['Scoring','Offline exact JSON comparison with pinned reviewer answers. No LLM answer judge, answer repair or model-call replay.'],
        ['Verifier input','Declaration and produced output only; no original user input or reviewer answers.'],
        ['Scope','Router/model-bridge component comparison, not complete admitted research-DAG or frontend acceptance.'],
        ['Host','gx10-004d / DGX Spark / NVIDIA GB10. Local models run on Spark; subscription inference is remote.'],
        ['Timing limits','Shared host, sequential arm order and overlapping application image builds; no controlled latency, peak-memory or power claim.']])
    r.p('The policy and candidates were refined on these public development fixtures. Matching 24/24 observed worker answers is not a statistical equivalence result or a claim of general performance on unseen tasks. Different tokenizers and subscription wrapper overhead affect token comparisons. Monetary costs and savings were not measured.')
    r.table(['Local candidate','Precision','Direct development qualification'],[
        ['gpt-oss-20b','MXFP4','8/8 once; assessor, eligible worker and separate verifier'],
        ['Nemotron 3.5 Lightning 30B-A3B','Q4_0','8/8 once; all six local workers in this campaign'],
        ['gpt-oss-120b','MXFP4','8/8 once; eligible but not selected as a worker in this campaign']])
    r.p('Candidate qualification is a separate, single-repeat observation on the same development fixtures; it does not establish universal model superiority. Model revisions, file hashes and resource ceilings are included in the pool selection data.')
    r.h('Reproducibility and source identity')
    r.table(['Field','Identity'],[
        ['Measured image',json.loads((ROOT/'source-provenance.json').read_text())['app_image']],
        ['Source manifest SHA-256',json.loads((ROOT/'source-provenance.json').read_text())['source_manifest_sha256']],
        ['Source Git base',json.loads((ROOT/'source-provenance.json').read_text())['base_commit']+'; dirty source overlay identified by inventory/image'],
        ['Reference plan SHA-256',COHORTS[0]['plan_sha256']],['Hybrid plan SHA-256',COHORTS[1]['plan_sha256']],
        ['Original public source-plan SHA-256',SOURCE['source_plan_sha256']],
        ['Reviewer pin, answers not exported',SOURCE['reviewer_sha256']],
        ['Native evidence','42 subscription executions checked: 24 reference + 18 hybrid; original prompt hash, resolved model, medium effort and completed terminal event.']])
    r.p('The measured image is distinguished from the later released image. The release changed two locale files, documentation and one readiness explanatory string; the routing and benchmark call path were unchanged. Original receipts and native packets remain on Spark. Exported call summaries are explicitly labeled projections, not complete receipts.')
    for label,target in [('Measurements and observation index',f'data/{data_name}'),('Flat observation metrics','data/observations.csv'),
        ('Unmodified public input/output manifest','data/originals/manifest.json'),('Call/dispatch receipt projections','data/receipt-projections.json'),
        ('Local model pins','data/pool-selection.json'),('Separate candidate qualification','data/candidate-qualification.json'),('Measured source provenance','data/source-provenance.json'),('Released image provenance','data/release-provenance.json'),
        ('Data definitions and integrity checks','README.md')]:r.link(label,target)


def external_report(folder):
    r=Report(folder,'AI4R Hybrid v8: Same Observed Worker Accuracy, 18.19% Fewer Tokens','External presentation · Worker-answer benchmark')
    r.p('External presentation | measured and prepared 27 October 2026')
    r.p('**18.19% fewer reported tokens, with both arms answering 24/24 assignments correctly.** Hybrid v8 used 200,227 tokens versus 244,732 for fixed ChatGPT inside AI4R: 44,505 fewer tokens, including selection and independent verification overhead. All eight fixtures matched reference worker correctness. This is an observed result on a small development set, not demonstrated general accuracy equivalence.',True)
    r.fig('01-efficiency-and-accuracy.png','Figure 1. Both arms reached 100% observed worker-answer accuracy; Hybrid v8 used fewer total adapter-reported tokens.')
    r.h('1. Matched AI4R reference')
    r.p('The reference now uses subscription ChatGPT as the fixed worker inside AI4R. Both arms share the same model bridge, independent gpt-oss-20b verification and structural check. This replaces the historical direct-ChatGPT comparison for the current campaign. The report measures generated worker answers and component resource use, not end-to-end user delivery.')
    r.table(['Metric',*LABELS],[['Observations','24','24'],['Exact-correct worker answers','24/24 (100%)','24/24 (100%)'],
        ['Total reported tokens','244,732','200,227'],['Token reduction','Reference','44,505 (18.19%)'],
        ['Worker dispatch','24 ChatGPT','18 ChatGPT + 6 Lightning'],['Model calls, all roles','48','54'],
        ['Cumulative observed component time','271.16 s','313.69 s'],
        ['Median per observation',*[f"{statistics.median(x['elapsed_s'] for x in ROWS if x['arm']==a):.2f} s" for a in ARMS]],
        ['Monetary cost / savings','Not measured','Not measured']])
    r.p('Hybrid used 25% fewer subscription worker calls, while retaining all observed exact-correct worker answers. It took 42.53 seconds more cumulatively in this campaign. No latency improvement, dollar saving or broad quality-equivalence claim is made.')
    r.h('2. Complete token accounting and actual routing')
    r.fig('02-token-accounting-and-routing.png','Figure 2. Both arms include verifier usage; all six hybrid selector calls are also counted.')
    r.table(['Role','Reference input / output / total','Hybrid input / output / total'],[
        [label,*[' / '.join(f"{c['roles'].get(role,{}).get(k,0):,}" for k in ['input_tokens','output_tokens'])+f" / {role_total(c,role):,}" for c in COHORTS]]
        for role,label in [('worker','Worker'),('verifier','Verifier'),('routing_selection','Selector')]])
    r.p('gpt-oss-20b performed six successful selection calls; all six selected Lightning, which answered correctly. Protected task-risk rules routed the other eighteen workers directly to ChatGPT. No selector failed or required fallback. gpt-oss-120b remained an eligible candidate; it was not selected as a worker in this campaign.')
    r.h('3. Fixture-level worker results')
    r.fig('03-per-fixture-results.png','Figure 3. Both arms answered all three repeats of every fixture correctly, including c01-inference.')
    r.table(['Fixture',*LABELS],[[v,*[f"{sum(x['correct'] for x in ROWS if x['arm']==a and x['variant']==v)}/3" for a in ARMS]] for v in VARIANTS])
    r.p('All three c01 hybrid workers used actual GPT-6.1-Sol and returned the correct threshold result. This addresses the earlier routing weakness on this development fixture through general risk rules, not a case-specific answer or post-failure retry.')
    common_sections(r)
    r.finish()


def internal_report(folder):
    r=Report(folder,'AI4R Internal Benchmark: Equal Worker Accuracy, Persistent Verifier False Blocks','Internal presentation · Verifier/gate diagnostics')
    r.p('Internal presentation | measured and prepared 27 October 2026')
    r.p('**The routing changes preserved 24/24 worker correctness, but each arm lost four correct answers at the gate.** Fixed ChatGPT and Hybrid v8 each advanced only 20/24 correct answers (83.33%). Hybrid used 18.19% fewer total reported tokens. The verifier defect remains; no FAIL was overridden and these are component outcomes, not completed product Delivery.',True)
    r.fig('01-gate-false-blocks.png','Figure 1. Each arm blocked 4 of 24 correct answers: a 16.67% false-block rate among correct answers.')
    r.h('1. Worker quality and gate outcome are separate')
    r.table(['Metric',*LABELS],[['Exact-correct worker answers','24/24','24/24'],['Correct + advanced','20/24 (83.33%)','20/24 (83.33%)'],
        ['Correct + blocked','4/24 (16.67%)','4/24 (16.67%)'],['Incorrect answers in sample','0','0'],
        ['Wrong-answer rejection capability','Not established: no wrong worker answers','Not established: no wrong worker answers'],
        ['Actual verifier replies','20 PASS / 4 FAIL','20 PASS / 4 FAIL'],['Failed model calls / selector fallbacks','0 / 0','0 / 0']])
    r.p('A correct generated answer is not a completed delivery. Conversely, zero incorrect answers advancing in this sample is not evidence that the verifier detects wrong answers: no incorrect worker answer was observed.')
    r.h('2. Every false block')
    r.fig('02-false-blocks-by-fixture.png','Figure 2. The equal aggregate rates conceal different blocked fixtures and repeats.')
    r.table(['Fixture','Reference correct / advanced / blocked','Hybrid correct / advanced / blocked'],[
        [v,*[f"{sum(x['correct'] for x in ROWS if x['arm']==a and x['variant']==v)} / {sum(x['correct'] and x['gate']=='advance' for x in ROWS if x['arm']==a and x['variant']==v)} / {sum(x['correct'] and x['gate']!='advance' for x in ROWS if x['arm']==a and x['variant']==v)}" for a in ARMS]] for v in VARIANTS])
    r.p('Repeat numbers below are zero-based. Exact worker/verifier strings and source receipt hashes are retained in the internal data. All eight false blocks were explicit verifier FAIL replies, not absent model responses.')
    r.table(['Arm / fixture / repeat','Actual worker','Worker output (exact)','Verifier output (exact)'],[
        [f"{x['arm']} / {x['variant']} / {x['repeat']}",x['selected'],x['worker_output'],x['verifier_output']]
        for x in ROWS if x['correct'] and x['gate']!='advance'])
    r.h('3. Verified behavior and diagnosis limits')
    r.p('The gpt-oss-20b verifier receives only the generic component declaration and produced JSON. It does not receive user input values, the original task or reviewer answers. The harness advances only for an exact decoded {"verdict":"PASS"}; otherwise it halts. All 48 verifier model calls completed, and all eight halts were decoded FAIL replies.')
    r.p('Baseline c05 repeats produced the same correct worker text, yet repeat 0 passed and repeats 1/2 failed. The observed inconsistency is real. The one-field verdict carries no criterion or reason, so the campaign cannot establish why each rejection occurred. The shared generic declaration lacks fixture-specific output fields and source-independent acceptance predicates; underspecification and unjustified judgments about hidden facts are plausible contributors, not proven single causes.')
    r.p('Both arms used the same verifier configuration, but stochastic decisions and different per-request outputs can change verdicts and token use. Equal 20/24 totals do not establish equivalent gate behavior. These are generic component-verifier findings, not evidence that every admitted production Capsule verifier has the same failure.')
    r.h('4. Router repair and total token cost')
    r.fig('03-full-token-accounting.png','Figure 3. The saving survives selection and verifier overhead; both reference and hybrid include independent verification.')
    r.table(['Role','Reference tokens / calls','Hybrid tokens / calls'],[
        [label,*[f"{role_total(c,role):,} / {c['roles'].get(role,{}).get('calls',0)}" for c in COHORTS]]
        for role,label in [('worker','Worker'),('verifier','Verifier'),('routing_selection','Selector')]])
    r.p('The reference totals 244,732 tokens; hybrid totals 200,227, saving 44,505 (18.19%). Verifier usage was 17,693 versus 14,471 tokens; hybrid additionally spent 9,590 selector tokens. The verifier difference is an observation, not proof that routing itself made verification cheaper. Historical v5 used a direct reference without verifier overhead; its headline savings must not be treated as the same matched comparison.')
    r.p('The former c01 routing failure did not recur: all three hybrid attempts used ChatGPT, answered correctly and advanced. The six actual local workers were Lightning and all answered correctly. Every selector completed successfully. The new pool contains gpt-oss-20b, Lightning and gpt-oss-120b; no Qwen worker is in the current automatic pool.')
    r.h('5. Remaining repair boundaries — not changed by this report')
    r.table(['Area','General repair to consider','Required evidence'],[
        ['Declarations','Define output schema and source-independent semantic criteria; preserve the declaration/output-only verifier boundary.','Each decision can name an observable declared criterion.'],
        ['Verifier response','Version the response if adding criterion IDs, reasons or an uncheckable disposition.','Raw verdict reasons distinguish actual contradiction from unavailable source evidence.'],
        ['Decision stability','Evaluate repeated identical declaration/output pairs with a frozen reviewer configuration.','Stable behavior without case IDs, gold-answer exposure or forced PASS.'],
        ['Gate','Keep deterministic control and explicit blocking.','Malformed, unavailable and negative outcomes are never silently advanced.'],
        ['Acceptance','Measure unseen tasks and a separate admitted frontend-to-Delivery run after general repairs.','Do not substitute component worker correctness for product delivery.']])
    common_sections(r,'assessment.json')
    r.finish()


def datasets(folder, internal):
    data=folder/'data';data.mkdir(parents=True,exist_ok=True)
    if internal:
        shutil.copyfile(ROOT/'assessment.json',data/'assessment.json')
        rows=ROWS
    else:
        arm_fields=['observations','worker_correct','choices','selection_methods','roles','total_tokens','elapsed_s','native_proofs_checked','plan_sha256']
        row_fields=['arm','variant','repeat','correct','selected','selection_method','elapsed_s','worker_output','receipt_sha256']
        rows=[{k:x[k] for k in row_fields} for x in ROWS]
        write_json(data/'measurements.json',{'schema':'ai4r-external-worker-benchmark:2',
            'scope':'Hybrid v8 versus fixed ChatGPT inside AI4R; generated worker answers and resources, not end-to-end delivery.',
            'measurement_date':'2026-10-27','prepared_date':'2026-10-27',
            'source_assessment_sha256':hashlib.sha256((ROOT/'assessment.json').read_bytes()).hexdigest(),
            'source_plan_sha256':SOURCE['source_plan_sha256'],'reviewer_sha256':SOURCE['reviewer_sha256'],
            'reviewer_answers_exported':False,'monetary_cost':None,
            'arms':{a:{k:SOURCE['arms'][a][k] for k in arm_fields} for a in ARMS},'observations':rows})
    fields=['arm','variant','repeat','correct','selected','selection_method','elapsed_s','receipt_sha256']
    if internal:fields+=['gate','verifier_output']
    with (data/'observations.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    for name in ['source-provenance.json','release-provenance.json','local-qualification.json']:
        if name=='local-qualification.json' and not internal:continue
        shutil.copyfile(ROOT/name,data/name)
    shutil.copyfile(REPO/'deploy/m1/spark-pool-v3.json',data/'pool-selection.json')
    qualification=json.loads((ROOT/'local-qualification.json').read_text())
    write_json(data/'candidate-qualification.json',{
        'scope':'One direct observation per public development fixture; separate from the matched campaign, not held-out.',
        'source_sha256':hashlib.sha256((ROOT/'local-qualification.json').read_bytes()).hexdigest(),
        'models':{**{k:qualification['large_models']['models'][k] for k in ['lightning','gptoss']},
            'gptoss20':{k:qualification['gptoss20'][k] for k in ['observations','correct','rows']}}})
    shutil.copytree(PUBLIC/'originals',data/'originals',dirs_exist_ok=True)
    shutil.copyfile(PUBLIC/'receipt-projections.json',data/'receipt-projections.json')
    (folder/'README.md').write_text('''# Report package

Open **benchmark-report.html** for the illustrated report. Charts are embedded;
no network or web server is needed to read it. Markdown and separate PNG figures
are also included. Data links refer to files inside this package.

The external view presents worker-answer performance and complete role-token
accounting. The internal view additionally preserves every verifier/gate outcome.
Neither view claims full research-workflow or frontend acceptance.

`data/originals` contains 104 byte-for-byte public input/request, original worker
answer and frozen campaign metadata files. Its manifest records their SHA-256.
`receipt-projections.json` contains 48 explicitly labeled call/dispatch projections,
not full original receipts. Full receipts and native packets remain on Spark.
The observation index retains each source receipt SHA-256; reviewer answers,
credentials, account files and auth packets are not included.

`checksums.json` covers every package file except itself. The ZIP has a separate
SHA-256 sidecar. Reports use existing measurements; no new inference was run.
''',encoding='utf-8')


def package(folder):
    files={p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='checksums.json'}
    write_json(folder/'checksums.json',{'algorithm':'sha256','files':files})
    target=folder.with_suffix('.zip')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(folder.parent).as_posix())
    target.with_suffix('.zip.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n',encoding='ascii')
    return {'folder':str(folder),'zip':str(target),'bytes':target.stat().st_size,'files':len(files)+1}


def main():
    assert len(ROWS)==48 and SOURCE['total_token_reduction']==1-200227/244732
    for a,c in zip(ARMS,COHORTS):
        rows=[r for r in ROWS if r['arm']==a]
        assert len(rows)==24 and sum(r['correct'] for r in rows)==c['worker_correct']==24
        assert sum(r['correct'] and r['gate']=='advance' for r in rows)==c['gated_correct']==20
        assert sum(role_total(c,k) for k in c['roles'])==c['total_tokens']
    external=OUTPUT/'AI4R_Hybrid_v8_External_2026-10-27'
    internal=OUTPUT/'AI4R_Hybrid_v8_Internal_2026-10-27'
    for folder in [external,internal]:folder.mkdir(parents=True,exist_ok=True)
    figures(external,internal)
    datasets(external,False);datasets(internal,True)
    external_report(external);internal_report(internal)
    print(json.dumps([package(external),package(internal)],indent=2))


if __name__=='__main__':main()
