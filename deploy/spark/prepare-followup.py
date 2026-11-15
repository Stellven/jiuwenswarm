"""Operator-side preparation of a diagnostic follow-up; no automatic admission."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jiuwenswarm.factory.contract import atomic_json
from jiuwenswarm.factory.store import Store


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--home',type=Path,default=Path('/home/user2/software-factory-spark-20261113/mission-store'))
    p.add_argument('--source-task',default='spark-strata-e2e-001')
    p.add_argument('--task',default='spark-decoder-followup-001')
    p.add_argument('--objective',default='Make the decoder faster.')
    a=p.parse_args()
    with Store(a.home) as s:
        previous=s.get_task(a.source_task);data=s.dump(a.source_task)
        state_path=a.home/'sessions'/(a.source_task+'.state.json')
        state=json.loads(state_path.read_text())
        if state.get('outcome') not in {'accept','report_inconclusive','stop_missing_prerequisite','partial'}:
            raise ValueError('Finish/review the previous mission before preparing follow-up')
        completed=[o['obs_id'] for o in data['observations'] if o['kind']=='lab_result' and o['values'].get('execution_outcome')=='ok']
        if not completed:raise ValueError('No verified successful lab results to review')
    remaining=24-state['turns']
    if remaining<1:raise ValueError('Original 24-turn campaign allowance exhausted')
    task=dict(task_id=a.task,objective=a.objective,allowed_effects=['process.exec','workspace.read'],
        target=previous['target'],budget={'max_turns':min(4,remaining),'wall_clock_s':600},
        constraints=dict(read_tasks=[a.source_task],methodology_driven=True,attempt_limits={'build':0,'lab':0},
            contract_sha256=previous['constraints']['contract_sha256'],
            diagnostic_only=True,required_output='One evidence-backed hypothesis and proposed next input; no engine runs, edits, contract changes or automatic promotion.'),
        contract_id=previous['contract_id'],initial_run_config={'env':{}},
        component_cc='factory.methodology_diagnosis',capability_cc='factory.methodology_followup',source=previous['source'],
        operator_labels=dict(source_task=a.source_task,verified_report_ids=completed,
            report_instruction='Read the source task reports and decisions, discover available CCs, and choose the next experiment. The prior task failures stay historical evidence; review cited host repairs and successful successor runs.'))
    path=a.home/(a.task+'.task.json')
    if path.exists():raise ValueError('Follow-up input already exists; review it rather than overwriting')
    atomic_json(path,task)
    print(json.dumps(dict(proposed_task_file=str(path),status='prepared_not_admitted',diagnostic_only=True,
        source_task=a.source_task,source_reports=completed,max_turns=task['budget']['max_turns'])))

if __name__=='__main__':main()
