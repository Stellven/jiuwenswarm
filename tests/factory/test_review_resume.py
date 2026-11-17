"""A repaired prerequisite must reach a real new turn, without budget reset."""
import asyncio
import json

from test_controller import rig, make_task, publish
from jiuwenswarm.factory.operator_notes import publish as operator_note


def test_operator_reopen_does_not_cancel_on_the_previous_terminal_decision(tmp_path,rig):
    make_task(tmp_path,rig,max_turns=5)
    async def first(request):
        publish(rig,'report_inconclusive')
        yield {'event_type':'chat.delta','content':'A prerequisite is unavailable.'}
    rig.facade=first
    assert asyncio.run(rig.run('t'))['outcome']=='report_inconclusive'
    old_state=rig._load('t')
    old_state.update(idle_turns=3,stop_reason='stalled: old prerequisite')
    rig._save('t',old_state)
    operator_note(rig.home,'t','Prerequisite repaired. Continue in the same task and budget.')
    saw_note=[]
    async def resumed(request):
        saw_note.append('Prerequisite repaired' in request.params['query'])
        reopened=rig._load('t')
        assert reopened['idle_turns']==0 and 'stop_reason' not in reopened
        await asyncio.sleep(.35)
        publish(rig,'accept')
        yield {'event_type':'chat.delta','content':'New accepting decision after repair.'}
    rig.facade=resumed
    assert asyncio.run(rig.run('t'))['outcome']=='accept'
    state=json.loads((rig.home/'sessions/t.state.json').read_text())
    assert saw_note==[True] and state['turns']==2
    assert len(state['operator_notes_delivered'])==1
