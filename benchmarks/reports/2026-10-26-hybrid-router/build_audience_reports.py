"""Create external and internal presentations of unchanged measured results.

No app changes or model inference. External = v5 worker performance versus
ChatGPT; internal = complete diagnostics, with verifier false blocks prominent.
"""
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
import zipfile

os.environ.setdefault('MPLCONFIGDIR', 'D:/ai4r-cache/matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

ROOT = Path(__file__).resolve().parent
SOURCE = json.loads((ROOT/'data/measurements.json').read_text(encoding='utf-8'))
ENV = json.loads((ROOT/'data/runtime.json').read_text(encoding='utf-8-sig'))
ALL = SOURCE['cohorts']
BY = {c['id']: c for c in ALL}
EXTERNAL = [BY['chatgpt'], BY['v5']]
V5 = [r for r in SOURCE['observations'] if r['cohort']=='v5']
OUTSIDE, INSIDE = ROOT/'external', ROOT/'internal'
BLUE, TEAL, RED, GREY, GOLD = '#355ca8', '#087f8c', '#b94d45', '#778398', '#d4a130'
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11, 'axes.spines.top':False,
    'axes.spines.right':False, 'axes.titleweight':'bold', 'text.color':'#19314e',
    'axes.labelcolor':'#314059', 'figure.facecolor':'white', 'savefig.facecolor':'white'})


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True)+'\n', encoding='utf-8')


def save(fig, folder, name):
    (folder/'figures').mkdir(parents=True, exist_ok=True)
    fig.savefig(folder/'figures'/name, dpi=160, bbox_inches='tight')
    plt.close(fig)


def external_figures():
    fig, axes = plt.subplots(1,2,figsize=(11.4,4.7),layout='constrained')
    labels = ['All ChatGPT','Hybrid v5']
    for ax, values, title, ylabel, maximum, suffix in [
        (axes[0],[100,87.5],'Observed worker-answer accuracy','Exact-correct answers (%)',116,'%'),
        (axes[1],[226986,198698],'12.46% fewer reported tokens','Input + output tokens',265000,'')]:
        bars=ax.bar(labels,values,color=[BLUE,TEAL],width=.58)
        for bar,value in zip(bars,values):
            label=f'{value:g}%' if suffix else f'{value:,.0f}'
            ax.text(bar.get_x()+bar.get_width()/2,value+maximum*.025,label,ha='center',weight='bold')
        ax.set(title=title,ylabel=ylabel,ylim=(0,maximum))
        ax.grid(axis='y',alpha=.13);ax.set_axisbelow(True)
    fig.text(.01,-.045,'24 observations per arm = eight public fixtures repeated three times. Accuracy gap: 12.5 percentage points.',fontsize=9,color=GREY)
    save(fig,OUTSIDE,'01-efficiency-and-accuracy.png')

    fig, axes = plt.subplots(1,2,figsize=(11.4,4.7),layout='constrained')
    bottom=np.zeros(2)
    for role,label,color in [('worker','Worker',BLUE),('routing_selection','Selector',GOLD),('verifier','Verifier',TEAL)]:
        values=np.array([sum(c['roles'].get(role,{}).get(k,0) for k in ['input_tokens','output_tokens']) for c in EXTERNAL])
        axes[0].bar(labels,values/1000,bottom=bottom/1000,color=color,width=.55,label=label)
        bottom+=values
    axes[0].set(title='Token accounting includes routing overhead',ylabel='Reported tokens (thousands)',ylim=(0,260))
    axes[0].legend(frameon=False,ncols=3,fontsize=9,loc='upper left')
    axes[0].grid(axis='y',alpha=.13);axes[0].set_axisbelow(True)
    axes[1].barh([0],[19],color=BLUE,label='ChatGPT subscription')
    axes[1].barh([0],[5],left=[19],color=TEAL,label='Local Qwen')
    axes[1].text(9.5,0,'19',ha='center',va='center',color='white',fontsize=22,weight='bold')
    axes[1].text(21.5,0,'5',ha='center',va='center',color='white',fontsize=22,weight='bold')
    axes[1].set(title='Hybrid v5: actual worker choices',xlabel='Worker calls',yticks=[],xlim=(0,24),ylim=(-1,1))
    axes[1].legend(frameon=False,loc='upper left',fontsize=9)
    fig.text(.01,-.045,'Direct ChatGPT: one worker call/observation. Hybrid: selector + worker + verifier. Token totals are not monetary costs.',fontsize=9,color=GREY)
    save(fig,OUTSIDE,'02-token-accounting-and-routing.png')

    variants=list(BY['v5']['domains'])
    matrix=np.array([[c['domains'][v] for c in EXTERNAL] for v in variants])
    fig,ax=plt.subplots(figsize=(8.5,5.9),layout='constrained')
    ax.imshow(matrix,cmap=ListedColormap(['#f1d8d2','#efdba5','#afcfca','#398b91']),vmin=0,vmax=3,aspect='auto')
    for i in range(8):
        for j in range(2):ax.text(j,i,f'{matrix[i,j]}/3',ha='center',va='center',fontsize=13,color='white' if matrix[i,j]==3 else '#19314e')
    ax.set(xticks=[0,1],xticklabels=labels,yticks=np.arange(8),yticklabels=variants,title='Seven of eight fixtures matched baseline correctness')
    ax.tick_params(length=0,pad=10)
    for spine in ax.spines.values():spine.set_visible(False)
    fig.text(.01,-.025,'Each cell counts exact-correct answers across three repeats of one fixture; these are development cases.',fontsize=9,color=GREY)
    save(fig,OUTSIDE,'03-per-fixture-results.png')


def internal_figures():
    fig,ax=plt.subplots(figsize=(10.5,4.8),layout='constrained')
    labels=['Correct + advanced','Correct + blocked','Incorrect + advanced','Incorrect + blocked']
    values=[11,10,0,3]
    bars=ax.bar(labels,values,color=[TEAL,RED,RED,GREY],width=.6)
    for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value+.3,str(value),ha='center',fontsize=15,weight='bold')
    ax.set(ylim=(0,14),yticks=range(0,15,2),ylabel='v5 observations',title='Primary defect: 10 correct answers were blocked')
    ax.grid(axis='y',alpha=.13);ax.set_axisbelow(True)
    fig.text(.01,-.045,'Offline correctness is independent of the Qwen verifier. Verdicts were real PASS/FAIL responses, not inferred scores.',fontsize=9,color=GREY)
    save(fig,INSIDE,'01-current-gate-defect.png')

    variants=list(BY['v5']['domains'])
    correct_advanced=[sum(r['correct'] and r['gate']=='advance' for r in V5 if r['variant']==v) for v in variants]
    false_block=[sum(r['correct'] and r['gate']=='halt' for r in V5 if r['variant']==v) for v in variants]
    wrong=[sum(not r['correct'] for r in V5 if r['variant']==v) for v in variants]
    fig,ax=plt.subplots(figsize=(10,5.6),layout='constrained')
    bottom=np.zeros(8)
    for values,label,color in [(correct_advanced,'Correct + advanced',TEAL),(false_block,'Correct + blocked',RED),(wrong,'Incorrect + blocked',GREY)]:
        ax.barh(np.arange(8),values,left=bottom,color=color,label=label)
        for i,value in enumerate(values):
            if value:ax.text(bottom[i]+value/2,i,str(value),ha='center',va='center',color='white',weight='bold')
        bottom+=values
    ax.set(yticks=np.arange(8),yticklabels=variants,xlim=(0,3),xticks=[0,1,2,3],xlabel='Three repeats per fixture',title='False blocks affected six otherwise correct fixtures')
    ax.legend(frameon=False,ncols=3,fontsize=9,loc='lower left',bbox_to_anchor=(0,1.03))
    save(fig,INSIDE,'02-false-blocks-by-fixture.png')

    fig,ax=plt.subplots(figsize=(10.5,4.8),layout='constrained')
    cohorts=[BY[i] for i in ['v3','v4','v5']]
    x=np.arange(3)
    ax.bar(x-.18,[c['correct'] for c in cohorts],.34,color=BLUE,label='Exact-correct worker answer')
    ax.bar(x+.18,[c['gated_correct'] for c in cohorts],.34,color=TEAL,label='Correct + gate advanced')
    for i,c in enumerate(cohorts):
        ax.text(i-.18,c['correct']+.4,str(c['correct']),ha='center')
        ax.text(i+.18,c['gated_correct']+.4,str(c['gated_correct']),ha='center')
    ax.set(xticks=x,xticklabels=['Hybrid v3','Hybrid v4','Hybrid v5'],ylim=(0,28),ylabel='Observations out of 24',title='Better worker accuracy did not yield better gated delivery')
    ax.legend(frameon=False,ncols=2,fontsize=9);ax.grid(axis='y',alpha=.13);ax.set_axisbelow(True)
    fig.text(.01,-.045,'Component gate outcomes only. No complete frontend-to-Delivery run was measured by this campaign.',fontsize=9,color=GREY)
    save(fig,INSIDE,'03-worker-versus-gated-correctness.png')


def inline(value):
    text=html.escape(str(value))
    text=re.sub(r'`([^`]+)`',r'<code>\1</code>',text)
    return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',text)


class Report:
    def __init__(self,folder,title,audience):
        self.folder,self.title,self.audience=folder,title,audience
        self.md,self.html=[],[]
        self.h(title,1)

    def h(self,text,level=2):
        self.md.append('#'*level+' '+text+'\n')
        self.html.append(f'<h{level}>{inline(text)}</h{level}>')

    def p(self,text,callout=False):
        self.md.append(('> ' if callout else '')+text+'\n')
        tag='aside' if callout else 'p'
        self.html.append(f'<{tag}>{inline(text)}</{tag}>')

    def table(self,headers,rows):
        self.md.extend(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |'])
        self.md.extend('| '+' | '.join(str(v).replace('|','\\|').replace('\n',' ') for v in row)+' |' for row in rows)
        self.md.append('')
        self.html.append('<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+inline(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>')

    def fig(self,name,caption):
        self.md.append(f'![{caption}](figures/{name})\n\n{caption}\n')
        img=base64.b64encode((self.folder/'figures'/name).read_bytes()).decode()
        self.html.append(f'<figure><img src="data:image/png;base64,{img}" alt="{html.escape(caption)}"><figcaption>{inline(caption)}</figcaption></figure>')

    def link(self,label,target):
        self.md.append(f'[{label}]({target})\n')
        self.html.append(f'<p><a href="{html.escape(target,quote=True)}">{html.escape(label)}</a></p>')

    def finish(self):
        css='''body{margin:0;background:#f1f5f9;color:#24364c;font:16px/1.72 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1120px;margin:36px auto;background:white;border-radius:18px;padding:46px 54px;box-shadow:0 8px 36px #2030470b}h1{font-size:39px;line-height:1.2;letter-spacing:-1px;color:#16314e}h2{font-size:25px;line-height:1.35;color:#1e466f;margin-top:42px;padding-top:20px;border-top:1px solid #e4eaf2}aside{background:#edf5fa;border-left:5px solid #087f8c;padding:22px 25px;border-radius:0 10px 10px 0;margin:25px 0}p{margin:17px 0}table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.6}th,td{padding:12px 13px;text-align:left;vertical-align:top;border-bottom:1px solid #e1e7f0;overflow-wrap:anywhere}th{background:#eaf0f7;color:#193b61}tr:nth-child(even){background:#f8fafc}.table-wrap{overflow-x:auto;margin:23px 0}figure{border:1px solid #e1e7f0;border-radius:12px;padding:14px;margin:28px 0}figure img{max-width:100%;height:auto;display:block;margin:auto}figcaption{font-size:13px;color:#63758a;padding:12px 8px 3px}code{background:#edf1f5;border-radius:3px;padding:2px 5px;overflow-wrap:anywhere}a{color:#245f96}footer{margin-top:35px;color:#728299;font-size:13px}@media(max-width:700px){main{margin:0;padding:24px 16px;border-radius:0}h1{font-size:30px}table{min-width:580px}}@media print{body{background:white}main{box-shadow:none;padding:0;margin:0}figure{break-inside:avoid}h2{break-after:avoid}}'''
        self.folder.mkdir(parents=True,exist_ok=True)
        (self.folder/'benchmark-report.md').write_text('\n'.join(self.md),encoding='utf-8')
        doc='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(self.title)+'</title><style>'+css+'</style></head><body><main>'+''.join(self.html)+'<footer>'+html.escape(self.audience)+' · Measurements: 26 Oct 2026 · Prepared: 27 Oct 2026 · No external assets.</footer></main></body></html>'
        (self.folder/'benchmark-report.html').write_text(doc,encoding='utf-8')


def external_data():
    cohort_fields=['id','label','n','correct','choices','roles','total_tokens','elapsed_s','median_s','domains','native_proofs','plan_sha256','controller_sha256','launched','monetary_cost']
    row_fields=['cohort','variant','repeat','correct','selected','elapsed_s','roles','worker_output','native_proofs','source_sha256']
    data={'schema':'ai4r-external-worker-benchmark:1','scope':'Worker-answer performance: Hybrid v5 versus direct ChatGPT; not end-to-end product acceptance.',
        'measurement_date':'2026-10-26','prepared_date':'2026-10-27','source_measurements_sha256':hashlib.sha256((ROOT/'data/measurements.json').read_bytes()).hexdigest(),
        'source_plan_sha256':SOURCE['source_plan_sha256'],'reviewer_sha256':SOURCE['reviewer_sha256'],'reviewer_answers_exported':False,
        'cohorts':[{k:c[k] for k in cohort_fields} for c in EXTERNAL],
        'observations':[{k:r[k] for k in row_fields} for r in SOURCE['observations'] if r['cohort'] in ['chatgpt','v5']]}
    write_json(OUTSIDE/'data/measurements.json',data)
    write_json(OUTSIDE/'data/runtime.json',ENV)
    fields=['cohort','variant','repeat','correct','selected','elapsed_s','input_tokens','output_tokens','total_tokens','source_sha256']
    with (OUTSIDE/'data/observations.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for r in data['observations']:
            row={k:r[k] for k in fields if k in r}
            row['input_tokens']=sum(v['input_tokens'] for v in r['roles'].values())
            row['output_tokens']=sum(v['output_tokens'] for v in r['roles'].values())
            row['total_tokens']=row['input_tokens']+row['output_tokens'];writer.writerow(row)
    return data


def external_report():
    r=Report(OUTSIDE,'AI4R Hybrid v5: Fewer Tokens, Strong Observed Answer Accuracy','External presentation · Worker-answer benchmark')
    r.p('External presentation | measured 26 October 2026 | prepared 27 October 2026')
    r.p('**12.46% fewer reported tokens, with 87.5% observed worker-answer accuracy.** Hybrid v5 answered 21/24 assignments correctly using 198,698 tokens, compared with 24/24 and 226,986 tokens for all ChatGPT. It matched baseline correctness on seven of eight fixtures. This is a measured token/quality trade-off: three fewer correct answers and 28,288 fewer reported tokens, not demonstrated accuracy equivalence.',True)
    r.fig('01-efficiency-and-accuracy.png','Figure 1. Hybrid v5 reduced adapter-reported tokens while retaining 87.5% of baseline answer accuracy on this development set.')
    r.h('1. Why hybrid routing')
    r.p('AI4R chooses an execution model for each bounded task rather than using subscription ChatGPT for every worker call. Local Qwen performs operation classification; protected host rules select either local Qwen or the signed-in ChatGPT 6.1 Sol transport. Hybrid v5 used Qwen for five worker calls and ChatGPT for nineteen. The hypothesis is that local execution can cover suitable work while reserving the stronger remote model for reasoning-intensive work.')
    r.p('The evaluation here covers the real router/model bridge and generated worker answers. It is not an end-to-end user-delivery benchmark or a claim that full AI4R workflows achieved these success rates. Hybrid v5 is the only hybrid configuration presented; all ChatGPT is retained as the reference arm.')
    r.h('2. Headline results')
    r.table(['Metric','All ChatGPT reference','Hybrid v5'],[
        ['Observations','24','24'],['Exact-correct worker answers','24/24 (100.0%)','21/24 (87.5%)'],
        ['Accuracy difference','Reference','12.5 percentage points lower'],['Total reported input + output tokens','226,986','198,698'],
        ['Token reduction','Reference','28,288 (12.46%)'],['Worker calls','24 ChatGPT','19 ChatGPT + 5 local Qwen'],
        ['Total model calls','24','72 (24 selector + 24 worker + 24 verifier)'],
        ['Cumulative observed component time','86.67 s','337.91 s'],['Median per observation','3.41 s','13.71 s'],
        ['Monetary cost / savings','Not measured','Not measured']])
    r.p('The result supports the narrower statement that hybrid routing reduced reported token use with a substantial portion of baseline answer quality retained. It does not establish equal quality: the absolute answer-accuracy gap is 12.5 percentage points. Hybrid v5 also took longer in this campaign. No latency improvement or monetary saving is claimed.')
    r.h('3. Token accounting and actual routing')
    r.fig('02-token-accounting-and-routing.png','Figure 2. All observed hybrid overhead is included in its token total. The worker split is based on captured dispatch decisions, not intended configuration.')
    r.table(['Role','All ChatGPT input / output','Hybrid v5 input / output'],[
        ['Selector','Not run','12,235 / 1,475'],['Worker','225,939 / 1,047','179,862 / 944'],
        ['Verifier','Not run','4,014 / 168'],['Total','226,986','198,698']])
    r.p('Token totals are the sums reported by the actual adapters, including selection and verification calls in Hybrid v5. The direct reference makes one worker call per assignment and has no extra review call. Different tokenizers, subscription wrapper overhead, and unreported reasoning accounting limit interpretation. These totals are not converted into dollars: subscription marginal price, local electricity and hardware amortization were not measured.')
    r.h('4. What tasks were used')
    r.table(['Benchmark property','Method'],[
        ['Source','MR01 public development fixtures from the original AI4Research benchmark archive.'],
        ['Coverage','Eight small technical fixtures: inference, retrieval, shortest path, performance, database, quorum, reliability and paired data.'],
        ['Repetition','Three repeats of each fixed input; 24 observations per arm. Repeats are not independent tasks.'],
        ['Input','Supplied public facts and a public fixture rule; one bounded JSON answer. No external tools or downloads.'],
        ['Scoring','Offline exact JSON comparison with frozen reviewer answers; no LLM answer judge or output repair. Reviewer answers were not sent to workers.'],
        ['Budgets','Worker 90 s / 1,024 output tokens; selector 15 s / 256 output tokens; verifier 60 s.'],
        ['Execution','Sequential component observations using the production routing and model bridge, isolated finite authority and fresh per-observation state.']])
    r.fig('03-per-fixture-results.png','Figure 3. Hybrid v5 matched all-ChatGPT correctness on seven fixtures; all three errors were repeats of the inference fixture.')
    r.table(['Fixture','All ChatGPT correct','Hybrid v5 correct'],[[v,f"{BY['chatgpt']['domains'][v]}/3",f"{BY['v5']['domains'][v]}/3"] for v in BY['v5']['domains']])
    r.p('All nineteen ChatGPT-routed hybrid worker calls were correct. Two of five Qwen worker calls were correct; the three incorrect Qwen calls were repeats of c01-inference. Thus the dataset indicates a specific routing weakness as well as a saving opportunity. It does not show that local execution is generally accurate for all simple-looking requests.')
    r.h('5. Environment and evidence')
    r.table(['Field','Recorded value'],[
        ['Local host','DGX Spark / gx10-004d; NVIDIA GB10'],['OS',ENV['os']],['GPU driver','580.178.04'],
        ['Docker server',ENV['docker']],['Local model','Qwen3.8-27B FP8; served ID ai4r-qwen-017b9c7af6b5.'],
        ['Subscription worker','gpt-6.1-sol, medium reasoning, packaged App Server 0.163.0. Subscription inference is remote, not executed on the Spark GPU.'],
        ['Source identity','Image ID + frozen plan/controller hashes identify the measured code; Git base has source overlays.'],
        ['Native model evidence','43 subscription executions checked: 24 reference + 19 hybrid. Prompt hash, resolved model, medium reasoning and completed terminal event verified.'],
        ['Measurement scope','Component observations, not document-upload, Planner DAG or POC application acceptance.']])
    r.table(['Arm','App image ID','Frozen plan SHA-256','Controller SHA-256'],[[c['label'],c['launched']['image_id'],c['plan_sha256'],c['controller_sha256']] for c in EXTERNAL])
    r.p('The full evidence index retains original receipt SHA-256 values. Original input request files, original worker output files and frozen campaign metadata are included byte-for-byte. Numerical observation tables and call summaries are explicitly labeled projections of the fuller internal receipts; they are not represented as complete original receipts. No account credentials, auth packets or reviewer answer file is included.')
    r.h('6. Interpretation and limits')
    r.p('These are public development fixtures used during policy refinement, not held-out evaluation. Eight distinct inputs are too few to establish broad quality equivalence, and three repeats do not turn them into 24 independent tasks. The observed 12.46% token reduction and 87.5% answer accuracy describe this campaign only. Shared-host contention, different call counts and sequential campaign order limit timing comparisons. Peak memory, power and monetary costs were not collected.')
    r.p('**Takeaway:** Hybrid v5 demonstrates a real, measurable way to reduce reported model-token use while preserving much of the reference answer quality on a small development set. The remaining accuracy gap is explicit. Broader quality claims require a frozen policy evaluated on new tasks.',True)
    r.h('7. Included data')
    r.link('Measurements and worker-performance evidence index','data/measurements.json')
    r.link('Flat observation metrics','data/observations.csv')
    r.link('Unmodified input/output file manifest','data/originals/manifest.json')
    r.link('Call and dispatch receipt projections','data/receipt-projections.json')
    r.link('Environment snapshot','data/runtime.json')
    r.link('Data definitions and integrity checks','README.md')
    r.finish()


def internal_report():
    r=Report(INSIDE,'AI4R Internal Benchmark: Verifier False Blocks in Hybrid v5','Internal diagnostic presentation')
    r.p('Internal presentation | measured 26 October 2026 | prepared 27 October 2026')
    r.p('**Priority defect: the verifier blocked 10 correct worker answers.** Hybrid v5 generated 21/24 exact-correct answers, but only 11/24 were both correct and gate-advanced. The gate halted all three incorrect answers and ten correct ones. This is a real component-verifier decision defect, not a chart/display issue or evidence of completed product Delivery.',True)
    r.fig('01-current-gate-defect.png','Figure 1. Offline gold scoring versus the actual v5 verifier/gate outcome. Correct answers were lost after generation.')
    r.h('1. Defect magnitude')
    r.table(['Measure','v5 result'],[
        ['Worker exact correctness','21/24 = 87.5%'],['Correct + gate advanced','11/24 = 45.83%'],
        ['Correct answers blocked','10/21 correct answers = 47.62%'],['False-block share of all observations','10/24 = 41.67%'],
        ['Correctness lost after the gate','10 observations = 41.67 percentage points of the 24-observation denominator'],
        ['Incorrect answers advanced','0/3 incorrect answers'],['All gate decisions','11 advance; 13 halt'],
        ['Verifier replies','11 exact {"verdict":"PASS"}; 13 exact {"verdict":"FAIL"}'],
        ['Selector / worker / verifier calls','24 / 24 / 24; all recorded completed']])
    r.table(['Offline worker correctness','Gate advance','Gate halt','Total'],[['Correct',11,10,21],['Incorrect',0,3,3],['Total',11,13,24]])
    r.h('2. Where correct answers were blocked')
    r.fig('02-false-blocks-by-fixture.png','Figure 2. False blocks affected six fixtures. Database had three correct answers and three verifier failures.')
    r.table(['Fixture','Worker correct','Correct + advanced','Correct + blocked','Incorrect + blocked'],[
        [v,sum(x['correct'] for x in V5 if x['variant']==v),sum(x['correct'] and x['gate']=='advance' for x in V5 if x['variant']==v),sum(x['correct'] and x['gate']=='halt' for x in V5 if x['variant']==v),sum(not x['correct'] and x['gate']=='halt' for x in V5 if x['variant']==v)] for v in BY['v5']['domains']])
    r.p('Every false block is listed below, using the actual worker text and verifier reply from the preserved observation index. Correctness is from offline exact JSON scoring against the frozen reviewer criteria, not a new model judge. Repeat numbers are zero-based.')
    r.table(['Fixture / repeat','Selected worker','Worker output (exact)','Verifier output (exact)'],[
        [x['variant']+' / '+str(x['repeat']),'ChatGPT' if x['selected'].startswith('subscription:') else 'Qwen',x['worker_output'],x['verifier_output']]
        for x in V5 if x['correct'] and x['gate']=='halt'])
    r.h('3. Verified behavior and limits of diagnosis')
    r.p('The component harness sends the independent Qwen verifier only a generic declaration and the produced JSON output. It does not send the original request, input values or reviewer answers. This preserves the required verifier boundary. The declaration requires a finite JSON object, supplied facts and no external tools, but does not define fixture-specific output fields or a source-independent semantic acceptance predicate.')
    r.p('The harness deterministically advances only when the decoded verifier reply equals {"verdict":"PASS"}; otherwise it halts. All thirteen observed halts were explicit FAIL replies. The ten false blocks therefore cannot be explained solely by JSON parsing, an absent response or a UI error. However, the one-field verdict contains no reason, and the campaign does not prove why Qwen rejected each answer. Declaration underspecification and unjustified source-fact judgments are plausible contributors, not established single causes.')
    r.p('This verifier is the generic benchmark component verifier. Its failures must not be silently generalized to every qualified production Capsule verifier. Conversely, a correct worker answer must not be counted as delivered merely because the model produced it. The component gate did control progression, and no failed verdict was bypassed.')
    r.h('4. Historical context and retained measurements')
    r.fig('03-worker-versus-gated-correctness.png','Figure 3. v5 improved worker correctness over v4 but advanced fewer correct answers. Preserving v5 is not a claim that it dominates every metric.')
    r.table(['Configuration','Worker correct','Correct + advanced','Correct + blocked','Wrong + advanced','Total tokens','Cumulative s'],[
        [c['label'],f"{c['correct']}/24",'N/A' if c['gated_correct'] is None else f"{c['gated_correct']}/24",'N/A' if c['gated_correct'] is None else c['correct']-c['gated_correct'],
         'N/A' if c['gated_correct'] is None else c['gates'].get('advance',0)-c['gated_correct'],f"{c['total_tokens']:,}",f"{c['elapsed_s']:.2f}"] for c in ALL])
    r.p('v5 used 198,698 reported tokens, 12.46% below direct all ChatGPT (226,986). It scored 87.5% worker accuracy versus 100%, took 337.91 s versus 86.67 s cumulatively and used 19 ChatGPT / 5 Qwen workers. Token totals include selector and verifier overhead for hybrid arms, while the direct ChatGPT reference has no reviewer. Monetary savings are not measurable from these receipts. All six configurations and 144 observation records remain in the internal dataset.')
    r.p('A separate routing defect remains: all three c01-inference repeats were assigned to Qwen and answered incorrectly. The task-operation selector sees summary/declaration/budget metadata, not the actual input values. This is separate from the ten correct-answer false blocks. No case-ID routing rule or gold-answer workaround is justified.')
    r.h('5. Recommended repair boundaries — not implemented by this report')
    r.table(['Work item','General pipeline change to consider','Evidence required'],[
        ['Declaration quality','Specify each Capsule output schema and source-independent semantic checks in its declaration. Do not inject user input or gold answers into the verifier.','Show the verifier can explain which declared criterion failed.'],
        ['Verifier behavior','Limit semantic assessment to observable output and declared obligations; do not invent inaccessible source facts. Distinguish failure from an uncheckable criterion if the contract allows it.','Correct known outputs are not rejected merely because the original source is hidden.'],
        ['Failure evidence','Version the verifier response contract if adding criterion IDs/reasons; preserve deterministic validation and existing record compatibility.','Stored reason and criterion trace each actual gate decision.'],
        ['Gate policy','Retain deterministic control. Do not force PASS, count blocked answers as delivered, or bypass Qwen failures.','Unknown, malformed and negative decisions remain explicit and governed.'],
        ['Routing descriptor','Provide sufficient general task structure to expose reasoning work without fixture IDs or answer leakage.','A frozen selector performs on new unseen fixtures.'],
        ['Acceptance scope','After fixing the general behavior, run a real frontend request through admitted CCs and Delivery, separately from component scoring.','Input, admitted workflow execution, gate outcomes and returned output trace the same run.']])
    r.h('6. Reproducibility, source identity and exclusions')
    r.p('This is offline analysis of already completed measurements; no model calls or app fixes were performed to produce these presentations. The dataset is public development MR01: eight fixtures repeated three times. Policies were refined on these fixtures; repeats are not independent tasks, and no held-out confidence or general bug-free claim is justified.')
    r.table(['Field','Value'],[['Host / GPU',SOURCE['host']+' / NVIDIA GB10'],['OS',ENV['os']],['Current measured v5 image',BY['v5']['launched']['image_id']],['v5 frozen plan SHA-256',BY['v5']['plan_sha256']],['v5 controller SHA-256',BY['v5']['controller_sha256']],['Reviewer criteria SHA-256',SOURCE['reviewer_sha256']],['Source record scope','Isolated component authority + real router/bridge, not Planner DAG acceptance.']])
    r.p('Earlier interrupted chatgpt-baseline-001 and hybrid-routing-001 are excluded from completed comparison scores; the complete arms use chatgpt-baseline-002 and hybrid-routing-002. The historical MR02 compatibility campaign did not complete. These exclusions and the older calibration observations remain documented in the unchanged original report. No full diagnostic receipt or reviewer answer file is included in the external presentation package.')
    r.h('7. Internal evidence files')
    r.link('Complete original measurement export (all six configurations)','data/measurements.json')
    r.link('Original flat observation table','data/observations.csv')
    r.link('Full original illustrated report','../benchmark-report.md')
    r.link('External worker-performance presentation','../external/benchmark-report.md')
    r.p('Per-observation source paths and SHA-256 values remain in the internal measurement JSON. Full native packets and component receipts remain on Spark. The external view omits this gate-diagnostic narrative and verdict data, but keeps the same worker accuracy, tokens, timings, routing choices and scope limitations.')
    r.finish()


def artifacts_and_package():
    for name in ['measurements.json','observations.csv','runtime.json']:
        (INSIDE/'data').mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'data'/name,INSIDE/'data'/name)
    (OUTSIDE/'README.md').write_text('''# External presentation package — Hybrid v5

Open `benchmark-report.html` directly, or read `benchmark-report.md` with its
local figures. Both reports are in English. No web server is required.

## Data included

- `data/originals/{chatgpt,v5}/`: 48 original public input requests, 48 original
  worker answers and eight original campaign metadata files (104 total).
  Their byte-for-byte SHA-256 values and source paths are in `manifest.json`.
- `data/measurements.json`: the 48-observation worker-performance projection,
  with offline correctness flags, model choices, role usage, timing and native
  proof summaries. Only Hybrid v5 and the all-ChatGPT reference are included.
- `data/receipt-projections.json`: captured model-call records and worker route
  decisions, explicitly extracted from fuller receipts. Source receipt hashes
  are retained. These are not complete diagnostic receipts.
- `data/observations.csv`: flat metrics; `data/runtime.json`: environment snapshot.
- `SHA256SUMS.txt`: package-file integrity hashes.

The complete internal dataset, diagnostic verdicts, reviewer answer file,
credentials and native authentication material are not in this package.
Offline correctness was scored against the frozen reviewer criteria; that
reviewer-only file is not distributed here, so the bundle cannot independently
recompute gold-answer correctness without authorized access to those criteria.

Token totals include all calls actually made in each arm. Subscription/local
tokenizers and wrapper overhead differ; token reductions are not dollar savings.
Worker-answer accuracy is not an end-to-end delivery success rate. The results
come from eight public development fixtures repeated three times, not held-out
or universal task evaluation. The measured 12.5-point accuracy gap is retained.
''',encoding='utf-8')
    for folder in [OUTSIDE,INSIDE]:
        paths=sorted(p for p in folder.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
        (folder/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(folder).as_posix()+'\n' for p in paths),encoding='utf-8')
    output=ROOT.parents[1]/'output'
    output.mkdir(exist_ok=True)
    name='AI4R_Hybrid_v5_External_Benchmark_2026-10-27'
    target=output/(name+'.zip')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(OUTSIDE.rglob('*')):
            if p.is_file():z.write(p,name+'/'+p.relative_to(OUTSIDE).as_posix())
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    (output/(name+'.zip.sha256')).write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n',encoding='utf-8')
    return target


if __name__=='__main__':
    assert len(V5)==24
    assert Counter((r['correct'],r['gate']) for r in V5)=={(True,'advance'):11,(True,'halt'):10,(False,'halt'):3}
    assert (OUTSIDE/'data/originals/manifest.json').is_file(), 'Collect the original public artifacts first.'
    external_figures();internal_figures()
    external_data();external_report();internal_report()
    archive=artifacts_and_package()
    print(json.dumps({'external':str(OUTSIDE/'benchmark-report.md'),'internal':str(INSIDE/'benchmark-report.md'),
        'zip':str(archive),'zip_bytes':archive.stat().st_size,'model_calls':0}))
