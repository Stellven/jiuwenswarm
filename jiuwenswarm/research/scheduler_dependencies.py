"""Shared predecessor gate for the research and Factory schedulers."""


def unaccepted_predecessors(predecessors, states, accepted_state):
    """Return the predecessor IDs that have yet to produce an accepted result."""
    return [identity for identity in predecessors if states.get(identity) != accepted_state]
