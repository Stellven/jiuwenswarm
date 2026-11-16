"""Conservative remaining resources, including failed and active reservations."""
import json
import time


def remaining_resources(store, task):
    base = getattr(store, '_store', store)
    from .loop import owned_attempts
    attempts = owned_attempts(base, task['task_id'])
    budget = task.get('budget', {})
    limits = task.get('constraints', {}).get('attempt_limits', {})
    controller = base.home / 'sessions' / (task['task_id'] + '.state.json')
    state = json.loads(controller.read_text()) if controller.exists() else {}
    elapsed = state.get('active_s', max(0,time.time()-task['created']))
    gpu = sum(a.get('resources', {}).get('job_class') == 'gpu' for a in attempts)
    result = dict(max_turns=max(0,budget.get('max_turns',0)-state.get('turns',0)),
                wall_clock_s=max(0,int(budget.get('wall_clock_s',0)-elapsed)),
                max_build_attempts=max(0,limits.get('build',budget.get('max_build_attempts',0))-sum(a['kind']=='build' for a in attempts)),
                max_completed_gpu_cells=max(0,budget.get('max_completed_gpu_cells',0)-gpu))

    owner_id=task.get('constraints',{}).get('campaign_budget_owner')
    if owner_id and owner_id != task['task_id']:
        owner=base.get_task(owner_id)
        related=[];turns=0
        for row in base._db.execute('SELECT task_id,constraints FROM tasks'):
            policy=json.loads(row['constraints'])
            if row['task_id']==owner_id or policy.get('campaign_budget_owner')==owner_id:
                related.append(row['task_id'])
                path=base.home/'sessions'/(row['task_id']+'.state.json')
                if path.exists(): turns+=json.loads(path.read_text()).get('turns',0)
        campaign_attempts={a['attempt_id']:a for name in related for a in owned_attempts(base,name)}.values()
        owner_budget=owner.get('budget',{});owner_limits=owner.get('constraints',{}).get('attempt_limits',{})
        result['max_turns']=min(result['max_turns'],max(0,owner_budget.get('max_turns',0)-turns))
        result['wall_clock_s']=min(result['wall_clock_s'],max(0,int(owner_budget.get('wall_clock_s',0)-(time.time()-owner['created']))))
        result['max_build_attempts']=min(result['max_build_attempts'],max(0,owner_limits.get('build',0)-sum(a['kind']=='build' for a in campaign_attempts)))
        result['max_completed_gpu_cells']=min(result['max_completed_gpu_cells'],max(0,owner_budget.get('max_completed_gpu_cells',owner_limits.get('lab',0))-sum(a['kind']=='lab' for a in campaign_attempts)))
    return result
