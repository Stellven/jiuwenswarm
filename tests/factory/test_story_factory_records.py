"""The story renders the factory's own records by what they say (node, output, outcome, reason)."""
from jiuwenswarm.factory.story import factory_record


def test_factory_records_say_what_happened():
    label, text, mark, noise = factory_record('node_check', dict(node_id='requant_2bit', output='pack_2bit', state='finished',
                                                                 passed=True, verifier=dict(stage_reached='native CC execution')))
    assert (label, mark, noise) == ('check', '✓', False) and text == 'requant_2bit.pack_2bit passed (native CC execution)'
    assert factory_record('node_check', dict(node_id='n', output='o', state='finished', passed=False, reason='no census'))[1:3] == (
        'n.o NOT passed: no census', '✗')
    run = factory_record('capped_run', dict(recipe='quantize', outcome='ok', seconds=8160, memory_cap='96G',
                                            request=dict(name='muse-2bit-v4'), result=dict(bytes=267e9)))
    assert run[1] == 'quantize muse-2bit-v4 · 267 GB · 136 min · cap 96G' and run[2] == '✓'
    stop = factory_record('capped_run', dict(recipe='serve', outcome='error', request=dict(label='smoke'),
                                             error=dict(code='MEMORY_LOW', message='available memory fell to 1.8 GiB')))
    assert stop[1].startswith('serve smoke stopped: MEMORY_LOW') and stop[2] == '✗'
    # an excuse names a failed attempt but is not itself a failure
    excused = factory_record('attempt_excused', dict(attempt_id='28cf7caf214c', node_id='build_base_engine', state='failed',
                                                     reason='host policy gap: fit filled unified memory'))
    assert excused[2] == '·' and 'as a host fault: fit filled unified memory' in excused[1]
    final = factory_record('node_contract_final', dict(node_id='requant_2bit', by='scheduler-agent',
                                                       final=dict(work=dict(bound_ccs=['weights.x', 'factory.capped_runner'])),
                                                       diff=[dict(path='stage'), dict(path='outputs.pack_2bit.criteria')]))
    assert final[1] == 'requant_2bit finalized by scheduler-agent · binds weights.x, factory.capped_runner · filled outputs.pack_2bit.criteria'
    assert factory_record('taskgraph_patch', {})[3] and factory_record('something_else', {}) is None
