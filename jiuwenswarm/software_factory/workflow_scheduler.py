"""Dispatch an admitted Factory task graph to its registered builders."""
from __future__ import annotations

from copy import deepcopy

from jiuwenswarm.research.scheduler_dependencies import unaccepted_predecessors

from .contracts import StageFailure


class WorkflowScheduler:
    """Schedule one validated graph using actual artifact-producer statuses."""

    def __init__(self, graph, nodes, dependencies, workers, dispatch, emit, graph_input, dependency_check):
        self.graph = graph
        self.nodes = {node['id']: node for node in nodes}
        self.dependencies = dependencies
        self.workers = workers
        self.dispatch = dispatch
        self.emit = emit
        self.graph_input = graph_input
        self.dependency_check = dependency_check
        self.dispatched = 0

    def run(self):
        opened = {'graph_path': 'graph.json', 'node_count': len(self.nodes), 'graph_input': self.graph_input,
                  'dependency_check': self.dependency_check,
                  'dispatch_gate': f'{unaccepted_predecessors.__module__}.{unaccepted_predecessors.__name__}'}
        if self.graph.get('id'):
            opened['graph_id'] = self.graph['id']
        self.emit('scheduler.started', opened)
        assignments = {identity: {'node_id': identity, 'dependencies': sorted(self.dependencies[identity]),
                                  **self.workers[identity]} for identity in self.nodes}
        self.emit('scheduler.assignments_ready', {'assignments': list(assignments.values())})

        # Preserve the admitted graph order whenever multiple nodes are ready.
        pending = dict(self.nodes)
        states = {identity: node['status'] for identity, node in self.nodes.items()}
        while pending:
            progressed = False
            for identity, node in tuple(pending.items()):
                dependencies = self.dependencies[identity]
                unfinished = unaccepted_predecessors(dependencies, states, 'verified')
                if any(states[key] in {'failed', 'blocked'} for key in unfinished):
                    node['status'] = 'blocked'
                    node['error'] = {'code': 'dependency_failed', 'message': 'A required producer did not verify'}
                    self.emit('node.blocked', {'node_id': identity, 'node': deepcopy(node)})
                elif not unfinished:
                    self.dispatched += 1
                    self.emit('scheduler.dispatched', assignments[identity])
                    self.dispatch(node)
                else:
                    continue
                states[identity] = node['status']
                del pending[identity]
                progressed = True
            if not progressed:
                raise StageFailure('scheduler_stalled', 'No pending node has a schedulable dependency state')

    def finish(self, status):
        self.emit('scheduler.finished', {'status': status, 'dispatched': self.dispatched})
