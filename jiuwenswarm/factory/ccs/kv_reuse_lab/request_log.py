"""Read initial prompt reuse from llama-server request logs."""

import re

TASK_LOG = re.compile(r'\bid\s+(\d+)\s*\|\s*task\s+(\d+)\s*\|\s*(.*)')
NEW_PROMPT = re.compile(r'\bnew prompt, .*?task\.n_tokens = (\d+)')
CACHED = re.compile(r'^cached n_tokens = (\d+), memory_seq_rm \[(\d+), end\)')


def first_cached_tasks(raw):
    """Return the first cache count after each request starts, with exact supporting log lines."""
    tasks = {}
    for line in raw.decode('utf-8', errors='replace').splitlines():
        match = TASK_LOG.search(line)
        if not match:
            continue
        slot_id, task_id = map(int, match.groups()[:2])
        message = match[3]
        key = (slot_id, task_id)
        if message.startswith('processing task, '):
            tasks[key] = dict(slot_id=slot_id, task_id=task_id, start=line)
        if key not in tasks:
            continue
        task = tasks[key]
        prompt = NEW_PROMPT.search(message)
        if prompt:
            task.update(prompt_tokens=int(prompt[1]), prompt_line=line)
        cached = CACHED.match(message)
        if cached and 'prompt_tokens' in task and 'cached_tokens' not in task:
            if cached[1] != cached[2]:
                raise ValueError('Server cache count disagrees with the memory erase start')
            task.update(cached_tokens=int(cached[1]), cache_line=line)
        if message.startswith(('restored context checkpoint', 'restoring context checkpoint')):
            task.setdefault('checkpoint_lines', []).append(line)
        if message.startswith('stop processing:'):
            task['end'] = line
    return list(tasks.values())
