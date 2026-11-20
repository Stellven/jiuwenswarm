"""Walk the seven presenter stops in Chromium. The optional live stop launches a fresh CPU-only audit."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

root=Path.home()/'predemo-spark'
base='http://100.105.127.48:5173'
task='spark-direct-benchmarks-20261120'
decision='spark-cache-predictor-postlab-plan-05:decision:1'
def utc(): return datetime.now(timezone.utc).isoformat()
def get(path):
    with urlopen(base+path,timeout=90) as response: return json.load(response)
cli=argparse.ArgumentParser(description=__doc__)
cli.add_argument('receipt',type=Path)
cli.add_argument('--live',action='store_true')
cli.add_argument('--name',default='final')
args=cli.parse_args()
pub=json.loads(args.receipt.read_bytes())
shots=root/'OPS/ui-shots'/args.name
shots.mkdir(exist_ok=True,parents=True)
source=Path(pub['export']).name
runs=get('/api/factory/runs')['runs']
rid=next(r['id'] for r in runs if r['source_name']==source and r['task_id']==task and r['kind']=='bundle')
live=next(r['id'] for r in runs if r['task_id']==task and r['kind']=='live')
citation_map=json.loads((Path(pub['export'])/'citation-map.json').read_bytes())
headline_ref=next(c for c in citation_map['direct_local_citations'] if c['source_path']=='OPS/final-headlines.json')
headline_sha=headline_ref['sha256']
headline_rows=json.loads((Path(pub['export'])/headline_ref['exported_path']).read_bytes())['rows']
if pub['status']=='final':
    assert hashlib.sha256((root/'OPS/final-headlines.json').read_bytes()).hexdigest()==headline_sha
result=dict(bundle=rid,url=base+'/#factory-run/'+rid,start=utc(),publication_id=pub['publication_id'],steps=[],page_errors=[],failed_factory_requests=[])
def save(): (shots/'rehearsal.json').write_text(json.dumps(result,indent=2)+'\n')
with sync_playwright() as pw:
    br=pw.chromium.launch(headless=True,args=['--disable-gpu'])
    page=br.new_page(viewport={'width':1512,'height':1050},locale='en-US')
    page.set_default_timeout(90000)
    expect.set_options(timeout=90000)
    page.on('pageerror',lambda err:result['page_errors'].append(str(err)))
    page.on('response',lambda response:result['failed_factory_requests'].append([response.status,response.url])
            if '/api/factory/' in response.url and response.status>=400 else None)
    page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
    page.route('https://fonts.gstatic.com/**',lambda r:r.abort())
    def go(key,expected):
        page.goto(base+'/#factory-run/'+key,wait_until='domcontentloaded')
        expect(page.get_by_test_id('factory-runs-run-title')).to_have_text(expected)
    def tab(name):
        page.locator(f'[data-testid="factory-runs-panel-tab"][data-variant="{name}"]').click()
    def shot(name,**extra):
        page.screenshot(path=str(shots/(name+'.png')))
        result['steps'].append(dict(name=name,verified_utc=utc(),url=page.url,**extra))
        save();print(name,flush=True)
    def check_table():
        table=page.get_by_test_id('factory-final-headlines')
        expect(table).to_have_attribute('data-sha256',headline_sha)
        expect(table.get_by_test_id('factory-final-headline-row')).to_have_count(len(headline_rows))
        return table
    go(rid,task)
    tab('overview');check_table()
    tab('contract')
    expect(page.get_by_test_id('factory-runs-file-content')).to_contain_text('star-deepseek-v1')
    shot('01-contract')
    tab('ontology')
    title=page.get_by_test_id('factory-runs-file-title')
    expect(title).to_be_visible()
    expect(page.get_by_test_id('factory-runs-file-content')).to_be_visible()
    shot('02-ontology',source=title.inner_text())
    page.goto(base+'/#capsules',wait_until='domcontentloaded')
    ccNames=['observability_event_recorder','weight_placement_planner','expert_weight_cache','expert_demand_predictor','batch_layout_mapper']
    counts=[]
    for i,name in enumerate(ccNames,1):
        card=page.locator(f'[data-testid="factory-runs-capsule-card"][data-variant="{name}"]')
        count=sum(1 for row in headline_rows if row['cc']==f'C{i}')
        expect(card.get_by_test_id('factory-capsule-headline-row')).to_have_count(count)
        counts.append(count)
    card=page.locator('[data-testid="factory-runs-capsule-card"][data-variant="expert_weight_cache"]')
    card.scroll_into_view_if_needed();shot('03-capsules',builder_rows=counts)
    card.click()
    expect(page.get_by_test_id('factory-runs-capsule-material-link').first).to_be_visible()
    go(live,task);tab('iterations')
    edge=page.get_by_test_id('factory-runs-successor').filter(has_text=decision)
    expect(edge.first).to_be_visible()
    candidates=edge.filter(has_text='cache60-build-overlap')
    line=candidates.first if candidates.count() else edge.first
    expand=line.get_by_text('Full rationale',exact=True)
    if expand.count():expand.first.click()
    line.scroll_into_view_if_needed()
    line.get_by_role('button',name=decision,exact=True).click()
    expect(page.get_by_test_id('factory-runs-iteration-linked-plan')).to_be_visible()
    shot('04-report-to-decision',decision=decision)
    go(rid,task);tab('measurements')
    table=check_table()
    expect(table).to_contain_text('90.80')
    expect(table).to_contain_text('96')
    table.scroll_into_view_if_needed();shot('05-measurements')
    tab('report')
    report=page.get_by_test_id('factory-runs-report')
    choice=report.get_by_test_id('factory-runs-report-select')
    if choice.count():choice.select_option(value='report.md')
    expect(report.get_by_test_id('factory-runs-report-markdown')).to_contain_text('How the recorder changed the next build')
    expect(report).to_contain_text('90.80')
    scrub=page.get_by_test_id('factory-runs-scrubber')
    scrub.focus();scrub.press('Home');scrub.press('ArrowRight')
    expect(page.get_by_test_id('factory-runs-position')).to_contain_text('1 /')
    scrub.press('End');last=int(scrub.get_attribute('max'))
    expect(page.get_by_test_id('factory-runs-position')).to_contain_text(f'{last} / {last}')
    report.scroll_into_view_if_needed();shot('06-report',replay_events=last)
    if args.live:
        page.get_by_test_id('factory-runs-launch-button').click()
        page.get_by_test_id('factory-runs-launch-template').select_option('recorder-evidence-walkthrough')
        page.get_by_test_id('factory-runs-launch-confirm').click()
        state=page.get_by_test_id('factory-runs-session-status')
        expect(state).to_be_visible()
        expect(state).to_have_attribute('data-variant','running',timeout=120000)
        new_id=page.url.split('#factory-run/')[-1].split('?')[0]
        expect(page.get_by_test_id('factory-runs-live')).to_be_checked()
        activity=page.get_by_test_id('factory-runs-overview-activity')
        activity.locator('summary').click()
        seen=[]
        for event in ('report-pinned','parity-checked','deepseek-trace-checked','granite-traces-checked','verification-complete'):
            item=activity.locator(f'[data-testid="factory-runs-event"][data-variant="{event}"]')
            expect(item.first).to_be_visible(timeout=75000)
            seen.append(dict(checkpoint=event,observed_utc=utc()))
            if event=='deepseek-trace-checked':
                shot('07-live-running',run_id=new_id)
        expect(state).to_have_attribute('data-variant','finished',timeout=60000)
        session=get('/api/factory/runs/'+new_id+'/session')
        detail=get('/api/factory/runs/'+new_id)
        receipt,=[f for f in detail['files'] if 'recorder-evidence-verification.json' in f.get('artifact_ids',[])]
        assert session['status']=='finished' and receipt['integrity']=='verified'
        shot('07-live-finished',run_id=new_id,status=session,checkpoints=seen,receipt=receipt)
    br.close()
result['stop']=utc()
save()
assert not result['page_errors'], result['page_errors']
assert not result['failed_factory_requests'],result['failed_factory_requests']
