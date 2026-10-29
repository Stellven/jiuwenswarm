"""Rebuild the English report and figures from captured receipts; no model calls."""
from collections import Counter
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import re

os.environ.setdefault('MPLCONFIGDIR', 'D:/ai4r-cache/matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT/'data/measurements.json').read_text(encoding='utf-8-sig'))
RUNTIME = json.loads((ROOT/'data/runtime.json').read_text(encoding='utf-8-sig'))
COHORTS = DATA['cohorts']
BY_ID = {c['id']: c for c in COHORTS}
ROWS = DATA['observations']
FIG = ROOT/'figures'
FIG.mkdir(exist_ok=True)
BLUE, TEAL, GOLD, RED, GREY = '#3659a8', '#087f8c', '#d5a130', '#be4d42', '#778498'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.labelcolor': '#314059', 'text.color': '#172b44', 'axes.titleweight': 'bold',
    'figure.facecolor': 'white', 'axes.facecolor': 'white', 'savefig.facecolor': 'white'})
LABELS = ['Fixed Qwen', 'E4B router\n(historical)', 'All ChatGPT', 'Hybrid v3', 'Hybrid v4', 'Hybrid v5\n(current)']


def save(fig, name):
    fig.savefig(FIG/name, dpi=170, bbox_inches='tight')
    plt.close(fig)


def figures():
    x = np.arange(6)
    fig, ax = plt.subplots(figsize=(11.5, 4.8), layout='constrained')
    raw = [c['correct']/24*100 for c in COHORTS]
    ax.bar(x-.18, raw, .34, color=BLUE, label='Exact-correct worker answer')
    for i, c in enumerate(COHORTS):
        ax.text(i-.18, raw[i]+1.5, f"{c['correct']}/24", ha='center', fontsize=10)
        if c['gated_correct'] is not None:
            value = c['gated_correct']/24*100
            ax.bar(i+.18, value, .34, color=TEAL)
            ax.text(i+.18, value+1.5, f"{c['gated_correct']}/24", ha='center', fontsize=10)
        else:
            ax.text(i+.18, 5, 'N/A*', ha='center', color=GREY, fontsize=9)
    ax.set(xticks=x, xticklabels=LABELS, ylim=(0, 117), yticks=[0,25,50,75,100],
           ylabel='Share of 24 observations (%)', title='Answer correctness and gate-qualified correctness are different')
    ax.legend(handles=[Patch(color=BLUE,label='Exact-correct worker answer'),
                       Patch(color=TEAL,label='Correct answer AND component gate advanced')],
              loc='upper left', ncols=2, frameon=False, fontsize=9)
    ax.grid(axis='y', alpha=.12); ax.set_axisbelow(True)
    fig.text(.01, -.045, '* All ChatGPT is a direct worker baseline with no verifier/gate. Eight fixtures × three repeats; public development data.', fontsize=9, color=GREY)
    save(fig, '01-correctness.png')

    fig, ax = plt.subplots(figsize=(11.5, 4.8), layout='constrained')
    bottom = np.zeros(6)
    for role, label, color in [('worker','Worker',BLUE),('routing_selection','Selector',GOLD),('verifier','Verifier',TEAL)]:
        values = np.array([sum(c['roles'].get(role,{}).get(k,0) for k in ['input_tokens','output_tokens']) for c in COHORTS])
        ax.bar(x, values/1000, bottom=bottom/1000, color=color, width=.62, label=label)
        bottom += values
    for i, value in enumerate(bottom):
        ax.text(i, value/1000+3, f'{int(value):,}', ha='center', fontsize=10)
    ax.set(xticks=x, xticklabels=LABELS, ylim=(0,265), ylabel='Reported input + output tokens (thousands)',
           title='Hybrid v5 used 12.46% fewer reported tokens than all ChatGPT')
    ax.legend(frameon=False, ncols=3); ax.grid(axis='y',alpha=.12); ax.set_axisbelow(True)
    fig.text(.01,-.045,'Adapter-reported tokens, not monetary cost. Direct ChatGPT has no review call; local/hybrid totals include review.',fontsize=9,color=GREY)
    save(fig,'02-token-budget.png')

    variants = list(COHORTS[0]['domains'])
    values = np.array([[c['domains'][v] for c in COHORTS] for v in variants])
    fig, ax = plt.subplots(figsize=(10,5.9),layout='constrained')
    ax.imshow(values,cmap=ListedColormap(['#f1d8d2','#efdba5','#aecfcb','#398b91']),vmin=0,vmax=3,aspect='auto')
    for i in range(8):
        for j in range(6):
            ax.text(j,i,f'{values[i,j]}/3',ha='center',va='center',color='white' if values[i,j]==3 else '#172b44',fontsize=12)
    ax.set(xticks=x,xticklabels=LABELS,yticks=np.arange(8),yticklabels=variants,
           title='All v5 errors came from the same inference fixture')
    ax.tick_params(length=0,pad=9)
    for spine in ax.spines.values():spine.set_visible(False)
    fig.text(.01,-.025,'Each row is one public fixture repeated three times. Cells are exact-correct worker answers, before the gate.',fontsize=9,color=GREY)
    save(fig,'03-domain-results.png')

    fig, axes = plt.subplots(1,2,figsize=(11.5,4.8),layout='constrained')
    hybrids = [BY_ID[i] for i in ['v3','v4','v5']]
    qwen = np.array([c['choices'].get('local:qwen',0) for c in hybrids])
    gpt = np.array([c['choices'].get('subscription:gpt-6.1-sol',0) for c in hybrids])
    axes[0].barh(np.arange(3),qwen,color=TEAL,label='Local Qwen')
    axes[0].barh(np.arange(3),gpt,left=qwen,color=BLUE,label='ChatGPT subscription')
    for i in range(3):
        axes[0].text(qwen[i]/2,i,str(qwen[i]),ha='center',va='center',color='white',weight='bold')
        axes[0].text(qwen[i]+gpt[i]/2,i,str(gpt[i]),ha='center',va='center',color='white',weight='bold')
    axes[0].set(yticks=np.arange(3),yticklabels=['Hybrid v3','Hybrid v4','Hybrid v5'],xlim=(0,24),xlabel='Worker selections (24 per policy)',title='Routing shifted toward ChatGPT')
    axes[0].legend(frameon=False,loc='lower left',bbox_to_anchor=(0,1.03),fontsize=9)
    current = [r for r in ROWS if r['cohort']=='v5']
    cells = np.array([[sum(r['correct'] and r['gate']=='advance' for r in current),sum(r['correct'] and r['gate']=='halt' for r in current)],
                      [sum(not r['correct'] and r['gate']=='advance' for r in current),sum(not r['correct'] and r['gate']=='halt' for r in current)]])
    axes[1].imshow(cells,cmap=ListedColormap(['#f4f7fa']),vmin=0,vmax=24,aspect='auto')
    cell_colors = [[TEAL,RED],[RED,GREY]]
    cell_labels = [['Correct + advanced','Correct + blocked'],['Incorrect + advanced','Incorrect + blocked']]
    for i in range(2):
        for j in range(2):
            axes[1].text(j,i,f'{cells[i,j]}\n{cell_labels[i][j]}',ha='center',va='center',fontsize=12,color=cell_colors[i][j],weight='bold',linespacing=1.8)
    axes[1].set(xticks=[0,1],xticklabels=['Gate advance','Gate halt'],yticks=[0,1],yticklabels=['Correct','Incorrect'],title='v5 gate blocked 10 correct answers')
    axes[1].tick_params(length=0,pad=10)
    for spine in axes[1].spines.values():spine.set_visible(False)
    fig.text(.01,-.045,'Gate results are from the generic component verifier. It received declaration + output only; no task inputs or gold answers.',fontsize=9,color=GREY)
    save(fig,'04-routing-and-gates.png')

    fig, ax = plt.subplots(figsize=(10,5),layout='constrained')
    offsets = {'qwen':(10,8),'e4b':(10,8),'chatgpt':(-60,12),'v3':(10,-20),'v4':(-90,8),'v5':(-30,-25)}
    for c in COHORTS:
        xx, yy = c['total_tokens']/1000,c['correct']/24*100
        ax.scatter(xx,yy,s=125,color=TEAL if c['id']=='v5' else BLUE,zorder=3,edgecolor='white',linewidth=1.2)
        ax.annotate(c['label'],(xx,yy),xytext=offsets[c['id']],textcoords='offset points',fontsize=10)
    ax.set(xlim=(0,255),ylim=(0,110),xlabel='Total reported input + output tokens (thousands; lower is better)',
           ylabel='Exact-correct worker answers (%)',title='Lower token use did not retain all-ChatGPT answer quality')
    ax.grid(alpha=.14); ax.set_axisbelow(True)
    fig.text(.01,-.04,'No fitted frontier or confidence interval: policies were iterated on these same eight development fixtures.',fontsize=9,color=GREY)
    save(fig,'05-quality-token-tradeoff.png')


MD, HTML = [], []


def inline(text):
    text = html.escape(str(text))
    text = re.sub(r'`([^`]+)`',r'<code>\1</code>',text)
    return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',text)


def heading(text, level=2):
    MD.append('#'*level+' '+text+'\n')
    HTML.append(f'<h{level}>{inline(text)}</h{level}>')


def paragraph(text, callout=False):
    MD.append(('> ' if callout else '')+text+'\n')
    HTML.append(f'<{ "aside" if callout else "p"}>{inline(text)}</{ "aside" if callout else "p"}>')


def table(headers, rows):
    MD.extend(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |'])
    MD.extend('| '+' | '.join(str(cell) for cell in row)+' |' for row in rows)
    MD.append('')
    HTML.append('<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+inline(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(cell)+'</td>' for cell in row)+'</tr>' for row in rows)+'</tbody></table></div>')


def figure(name, caption):
    MD.append(f'![{caption}](figures/{name})\n\n{caption}\n')
    encoded = __import__('base64').b64encode((FIG/name).read_bytes()).decode()
    HTML.append(f'<figure><img src="data:image/png;base64,{encoded}" alt="{html.escape(caption)}"><figcaption>{inline(caption)}</figcaption></figure>')


def link(label, target):
    MD.append(f'[{label}]({target})\n')
    HTML.append(f'<p><a href="{html.escape(target,quote=True)}">{html.escape(label)}</a></p>')


def report():
    v5, baseline = BY_ID['v5'], BY_ID['chatgpt']
    reduction = 100*(1-v5['total_tokens']/baseline['total_tokens'])
    heading('AI4R Hybrid Model Routing Benchmark',1)
    paragraph('26 October 2026 · DGX Spark + ChatGPT subscription · Public MR01 development fixtures')
    paragraph('**Decision: mixed-access routing works in the measured component, but the quality-preservation target is not met.** Current v5 produced 21/24 exact-correct worker answers (87.5%) using 198,698 reported tokens, 12.46% below the all-ChatGPT baseline. All ChatGPT answered 24/24 correctly. The independent component verifier blocked 10 correct v5 answers, leaving 11/24 both correct and gate-advanced.',True)
    paragraph('This report evaluates the real model-router/bridge component and its bounded verifier/gate. It does not certify a complete frontend → Intent Compiler → Planner → task Capsules → Delivery run. No paper-summary or ML experiment was part of this campaign. Measurements are real completed receipts; no missing prices, answers, or timings were filled in.')
    heading('1. What was measured')
    paragraph('The objective was to reduce reported token use relative to running every assignment on subscription ChatGPT 6.1 Sol, while retaining as much answer correctness as possible. Six configurations were compared on the same eight public technical fixtures, each repeated three times: 24 observations per configuration, 144 observations in the tables below. The three repeats reuse the same input; they are not three independent tasks.')
    table(['Item','Recorded method'],[
        ['Source','Original AI4Research benchmark ZIP, MR01 public development cases; source ZIP unchanged.'],
        ['Domains','Inference thresholds; retrieval; shortest path; performance; database; quorum; reliability; paired measurements.'],
        ['Task form','Bounded supplied facts and public fixture rule; one JSON answer; no tools, downloads, or external sources.'],
        ['Worker scoring','Offline exact JSON comparison with frozen reviewer answers: exact keys, ordered lists, finite numeric equality; no answer repair and no LLM judge.'],
        ['Reviewer isolation','Reviewer answers remained on the reviewer side. The collector used them offline to score outputs; the exported report data does not include gold answers.'],
        ['Verifier input','Capsule declaration + produced output only. User request, input values, and reviewer answers were hidden.'],
        ['Scheduling','Sequential observations, concurrency 1. New finite component state per observation.'],
        ['Budget','Worker: 90 s / 1,024 output tokens; verifier: 60 s. Hybrid selector: 15 s / 256 output tokens.'],
        ['Reported token metric','Sum of actual adapter-reported input + output tokens, including selector and verifier where present. No monetary cost inferred.']])
    paragraph('The local fixed/routed arms used the original local-routing component harness. Hybrid v3–v5 used an isolated ComponentAuthority wired to production AutomaticRouting, GovernedBridge, the local Qwen adapter, and the signed-in native ChatGPT owner. These are component observations, not admitted product Capsules or Planner-generated DAG runs. The direct all-ChatGPT arm has one worker call and no verifier; local/hybrid arms include Qwen verification. Consequently, total tokens and elapsed time compare the measured configurations, not equal-overhead end-to-end products.')
    heading('2. Results across all measured configurations')
    table(['Configuration','Worker correct','Correct + gate advanced','Reported tokens','Worker choices','Model calls'],[
        [c['label'],f"{c['correct']}/24 ({100*c['correct']/24:.1f}%)",'N/A: no gate' if c['gated_correct'] is None else f"{c['gated_correct']}/24",
         f"{c['total_tokens']:,}",', '.join(f'{n} '+{'local:qwen':'Qwen','local:e4b':'E4B','subscription:gpt-6.1-sol':'ChatGPT'}.get(k,k) for k,n in c['choices'].items()),
         sum(v['calls'] for v in c['roles'].values())] for c in COHORTS])
    figure('01-correctness.png','Figure 1. Worker answer correctness is distinct from correctness after the component gate. All-ChatGPT gated correctness was not measured.')
    paragraph('Historical E4B routing selected E4B for all 24 workers and answered only 3/24 correctly. Qwen self-selection in hybrid v3 shifted only one worker to ChatGPT and still scored 16/24. Difficulty-band routing in v4 increased raw correctness to 20/24. Operation classification in current v5 increased it to 21/24, but at higher token use than v4 and with fewer correct answers advanced by the gate. v5 is not an across-the-board improvement over v4.')
    table(['Hybrid version','ChatGPT workers','Qwen workers','Worker accuracy','Token reduction vs all ChatGPT','Correct + advanced'],[
        [c['label'],c['choices'].get('subscription:gpt-6.1-sol',0),c['choices'].get('local:qwen',0),f"{100*c['correct']/24:.1f}%",f"{100*(1-c['total_tokens']/baseline['total_tokens']):.2f}%",f"{c['gated_correct']}/24"] for c in [BY_ID['v3'],BY_ID['v4'],v5]])
    heading('3. Token use, time, and cost')
    figure('02-token-budget.png','Figure 2. Totals include the calls actually made. The subscription adapter reports substantial input overhead; tokens are not comparable monetary units across providers.')
    table(['Configuration','Selector in / out','Worker in / out','Verifier in / out','Cumulative time','Median / observation'],[
        [c['label'],*[f"{c['roles'][role]['input_tokens']:,} / {c['roles'][role]['output_tokens']:,}" if role in c['roles'] else 'Not run' for role in ['routing_selection','worker','verifier']],f"{c['elapsed_s']:.2f} s",f"{c['median_s']:.2f} s"] for c in COHORTS])
    paragraph(f"Current v5 saved {baseline['total_tokens']-v5['total_tokens']:,} reported tokens ({reduction:.2f}%) relative to all ChatGPT, with an answer-accuracy decrease of 12.5 percentage points. It made 72 calls: 24 Qwen selectors, 24 workers (19 ChatGPT + 5 Qwen), and 24 Qwen verifiers. Its cumulative component time was {v5['elapsed_s']:.2f} s versus {baseline['elapsed_s']:.2f} s for direct ChatGPT; it did not improve observed latency.")
    paragraph('**Monetary cost and monetary savings: unavailable.** There is no reliable per-request subscription marginal price or measured local power/amortization cost in these receipts. Provider tokenizers, subscription wrapper overhead, reasoning accounting, and local execution differ. These figures establish lower adapter-reported token totals, not a dollar saving. Shared-host contention, sequential campaign order, and unequal call counts also limit latency comparisons; no controlled wall-time speedup claim is made.')
    figure('05-quality-token-tradeoff.png','Figure 3. The observed quality/token trade-off on development fixtures. No statistical frontier or held-out generalization is claimed.')
    heading('4. Routing and verifier failures')
    figure('03-domain-results.png','Figure 4. Per-fixture exact correctness. Every current-v5 error is in c01-inference; the other seven fixtures scored 3/3.')
    paragraph('In v5, the router sent c01-inference to Qwen in all three repeats, and Qwen answered it incorrectly each time. The route rationale classified its operations as extraction/comparison/formatting. The selector sees a bounded task summary, declaration, candidate capabilities, and budget metadata, but not the actual input values. Insufficient task/structure information is a plausible explanation for the misclassification; this campaign does not establish it as the sole cause. Two other Qwen executions and all 19 ChatGPT executions were correct.')
    figure('04-routing-and-gates.png','Figure 5. Left: actual worker choices. Right: current-v5 gate outcomes checked against offline correctness, not against a model judge.')
    paragraph('The current verifier produced 13 halts and 11 advances. All 11 advanced answers were correct; all three wrong answers were halted. However, 10 of the 21 correct answers were also halted: 47.6% of correct answers were blocked. These were real verifier FAIL decisions, not just display errors. This generic declaration-only component verifier cannot establish source-fact correctness without input evidence; its result must not be reported as the offline answer score. Passing this component gate also does not prove full product Delivery succeeded.')
    table(['v5 output correctness','Gate advanced','Gate halted','Total'],[['Correct',11,10,21],['Incorrect',0,3,3],['Total',11,13,24]])
    paragraph('The main development priorities are a generally informative routing descriptor that reduces missed reasoning work without leaking reviewer answers, and verifier declarations/criteria that distinguish internal soundness from unverifiable source claims. User input must remain hidden from the verifier as requested. Neither issue should be patched with case IDs, answer lookup, forced gold decisions, or bypassed gates. A frozen policy should then be evaluated on genuinely new fixtures and on one complete app workflow.')
    heading('5. What is deployed and what this benchmark exercises')
    table(['Component','Current v5 behavior','Coverage here'],[
        ['Execution candidates','Local Qwen and subscription gpt-6.1-sol; E4B/Bolt shared services retained outside this execution pool.','Both access paths executed; 19 native ChatGPT and 5 Qwen workers.'],
        ['Selection','Qwen classifies a closed set of task operations; host rules choose a compatible worker. Router calls cannot recursively route themselves.','24 actual operation-selector calls; no fixture-specific dispatch code.'],
        ['Compatibility and dispatch','Candidate filtering and recorded decisions precede actual GovernedBridge dispatch; no post-failure switch to another worker.','Actual route decisions, model identities, and completed call records captured.'],
        ['Verifier','Fixed Qwen, separately accounted; declaration + output only.','24 actual verifier calls; their advance/halt results controlled the component gate.'],
        ['Run policy','At most four subscription CC invocations per run; some trusted Capsule scopes use predeclared routing rules.','Each benchmark observation contains one generic work CC. Multi-node quota behavior and trusted-scope routing are not exercised here.'],
        ['App integration','Same deployed AI4R service and Settings → Model; single local frontend endpoint 5175.','Component invoked via private native RPC, not frontend submission. Frontend and entire DAG acceptance are not established by these scores.']])
    paragraph('Planner remains a capability capsule. Model selection does not replace the Intent → Requirements → Planner → task Capsules → verifiers/gates → Delivery orchestration. This benchmark demonstrates dispatch through the real router and model bridge; it must not be used as proof that the entire orchestration completed without bugs.')
    heading('6. Environment and provenance')
    table(['Field','Value'],[
        ['Host',DATA['host']],['OS / architecture',RUNTIME['os']],['GPU / driver',RUNTIME['gpu']],
        ['Docker server',RUNTIME['docker']],['Local model','Qwen3.8-27B FP8; served ID ai4r-qwen-017b9c7af6b5; NVIDIA vLLM 26.09 configured runtime.'],
        ['Historical E4B','Nemotron 3.5 Bolt E4B Q4_K_M; served ID ai4r-e4b-1db54d5b1253; llama.cpp CUDA service.'],
        ['ChatGPT transport','Packaged Codex App Server 0.163.0; resolved model gpt-6.1-sol, reasoning medium. App Server is the subscription transport, not the AI4R orchestrator.'],
        ['Remote Git base',v5['launched']['base_commit']],['Source state','Dirty source overlays; base Git commit alone does not identify the measured code. Image IDs and controller hashes below identify each campaign.'],
        ['Current app image',RUNTIME['app_image']],['Current routing-source SHA-256',RUNTIME['current_routing_source_sha256']],
        ['Snapshot time (UTC)',RUNTIME['captured_at']],['Measurement export time (UTC)',DATA['collected_at']]])
    paragraph('GPU memory is reported as N/A by this unified-memory device query. No peak-memory or power metric was collected. The environment snapshot was taken after the campaigns and is not a per-observation utilization measurement. The all-ChatGPT worker runs remotely through the subscription; it does not run on the Spark GPU.')
    table(['Configuration','Campaign directory','Image ID'],[[c['label'],c['source_directory'],c['launched'].get('image_id','Original local campaign: code_pins in frozen plan')] for c in COHORTS])
    table(['Configuration','Frozen plan SHA-256','Controller SHA-256'],[[c['label'],c['plan_sha256'],c['controller_sha256'] or 'See original plan code_pins'] for c in COHORTS])
    paragraph('The collector verified the frozen reviewer-file hash, plan pins, and source-plan continuity before scoring. It checked canonical captured-record hashes and native-packet hashes, then matched the dispatched prompt hash, resolved gpt-6.1-sol model, medium reasoning, and completed terminal event. All 59 subscription executions across the direct baseline and hybrid v3–v5 had this native evidence (24 + 1 + 15 + 19). Authentication/account packets and credentials were not exported.')
    table(['Integrity item','SHA-256 / record'],[
        ['Original benchmark ZIP','d693481998808b5747cff37e4cc4ffccffa5a1cf9d33bc76b07c00a49f268d95'],
        ['Common source plan',DATA['source_plan_sha256']],['Reviewer-only MR01 criteria',DATA['reviewer_sha256']],
        ['Observation coverage','144 observations; 360 completed model calls in these six arms. Historical calibration calls are excluded from these tables.'],
        ['Native proof coverage','59 subscription executions; every exported native packet rehashed during report collection.']])
    heading('7. Interrupted attempts and limits')
    table(['Attempt / scope','Disposition'],[
        ['chatgpt-baseline-001','One real response preceded a host-side public-prompt hash mismatch caused by canonical key ordering. The controller was fixed; this interrupted batch was retained and excluded. The complete baseline is chatgpt-baseline-002.'],
        ['hybrid-routing-001','Started before the recreated app owner was ready; controller reported delivery unknown. No component/model observation was found. It was retained, not replayed. A readiness probe preceded new campaign hybrid-routing-002.'],
        ['Original local MR02','An earlier compatibility/fault campaign stopped on a router-timeout/uncertainty handling issue. It is not a completed MR02 acceptance result and is not included in these MR01 quality scores.'],
        ['Calibration observations','The historical original MR01 also had 72 calibration observations. They are outside the fixed/routed comparison arms summarized here; source campaign remains intact.'],
        ['Held-out/general tasks','Not measured. These public development fixtures were reused while refining routing policies. No independent-task confidence interval, universal accuracy claim, or unseen-task quality guarantee is justified.'],
        ['Complete AI4R workflow','Not established by this component campaign: no full Planner DAG, document upload, POC execution, or frontend Delivery acceptance measurement here.']])
    paragraph('**Conclusion:** the current hybrid system really dispatches to both local Qwen and subscription ChatGPT, with separately recorded selection, execution, and verification. On these development fixtures it reduces reported token use by 12.46% relative to all ChatGPT, while lowering raw accuracy from 100% to 87.5%. The gate advances only 11/24 correct outcomes, so neither quality preservation nor reliable gated delivery is demonstrated. These failures remain visible in the report and raw observation index.',True)
    heading('8. Files and reproduction')
    paragraph('The HTML report embeds all five figures and can be opened directly without a web server. Markdown references the same local PNG figures. The compact dataset contains actual worker/verifier outputs and source receipt hashes/paths, but no reviewer answer file or credential material. Full native packet receipts remain on Spark; the report contains verified proof summaries rather than another large packet archive.')
    link('Captured measurements and per-observation evidence index','data/measurements.json')
    link('Flat observation table','data/observations.csv')
    link('Post-campaign environment snapshot','data/runtime.json')
    link('Read-only Spark collector','collect_spark.py')
    link('Figure and report builder','build_report.py')
    link('Current production router source','../../../jiuwenswarm/research/automatic_routing.py')
    link('Component harness source','../../../jiuwenswarm/research/hybrid_benchmark.py')
    link('Subscription comparison controller','../../../deploy/m1/chatgpt_baseline.py')
    paragraph('To rebuild from the captured data, run: `python benchmarks/reports/2026-10-26-hybrid-router/build_report.py`. This performs no model inference. It requires matplotlib and numpy. To recollect the same completed receipts, run the collector with `--ssh user2@100.105.127.48 --output benchmarks/reports/2026-10-26-hybrid-router/data/measurements.json`; SSH access and the existing D-drive known-hosts file are required. Recollection is read-only and does not rerun the campaign.')
    (ROOT/'benchmark-report.md').write_text('\n'.join(MD),encoding='utf-8')
    css = '''body{margin:0;background:#f2f5fa;color:#203047;font:16px/1.7 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1180px;margin:36px auto;background:#fff;padding:48px 56px;border-radius:18px;box-shadow:0 8px 36px #2030470b}h1{font-size:40px;line-height:1.15;letter-spacing:-1.2px;color:#132943;margin-bottom:14px}h2{margin-top:48px;padding-top:18px;border-top:1px solid #e4eaf2;line-height:1.35;color:#193b61;font-size:25px}p{margin:16px 0}aside{background:#edf4fa;border-left:5px solid #087f8c;padding:22px 26px;margin:28px 0;border-radius:0 10px 10px 0}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.55}th{text-align:left;background:#eaf0f7;color:#193b61;font-weight:650}th,td{padding:12px 14px;border-bottom:1px solid #dfe6f0;vertical-align:top;overflow-wrap:anywhere}tr:nth-child(even){background:#f8fafc}.table-wrap{overflow-x:auto;margin:24px 0}figure{margin:30px 0;padding:16px;border:1px solid #e4eaf2;border-radius:12px}figure img{display:block;max-width:100%;height:auto;margin:auto}figcaption{font-size:13px;color:#5a6a80;padding:16px 10px 4px}code{background:#edf1f6;font-size:.9em;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}a{color:#215e9a}footer{margin-top:38px;color:#67778c;font-size:13px}@media(max-width:750px){main{margin:0;padding:25px 18px;border-radius:0}h1{font-size:30px}table{min-width:600px}}@media print{body{background:white}main{box-shadow:none;margin:0;padding:0;max-width:none}figure{break-inside:avoid}h2{break-after:avoid}a{color:inherit}}'''
    doc = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI4R Hybrid Routing Benchmark · 26 Oct 2026</title><style>'+css+'</style></head><body><main>'+''.join(HTML)+'<footer>AI4R · Captured measurements on D: · No external scripts, fonts, or image requests.</footer></main></body></html>'
    (ROOT/'benchmark-report.html').write_text(doc,encoding='utf-8')


def exports():
    fields = ['cohort','variant','repeat','correct','gate','selected','elapsed_s','input_tokens','output_tokens','total_tokens','source_path','source_sha256']
    with (ROOT/'data/observations.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        for row in ROWS:
            out = {k:row[k] for k in fields if k in row}
            out.update(input_tokens=sum(r['input_tokens'] for r in row['roles'].values()),output_tokens=sum(r['output_tokens'] for r in row['roles'].values()))
            out['total_tokens']=out['input_tokens']+out['output_tokens']
            writer.writerow(out)


if __name__=='__main__':
    figures()
    exports()
    report()
    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
    (ROOT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files),encoding='utf-8')
    print(json.dumps({'report':str(ROOT/'benchmark-report.html'),'figures':5,'observations':len(ROWS),'bytes':sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())}))
