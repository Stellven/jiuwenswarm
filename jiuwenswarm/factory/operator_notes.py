"""Append-only operator inbox, independent of an in-flight controller checkpoint."""
import json
from pathlib import Path
import re
import time
import uuid
from .contract import atomic_json


def directory(home, task_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',task_id):raise ValueError('Invalid task id')
    return Path(home)/'operator-inbox'/task_id


def publish(home, task_id, text):
    if not isinstance(text,str) or not text.strip():raise ValueError('Operator note must be nonempty text')
    note=dict(note_id=uuid.uuid4().hex,task_id=task_id,text=text,created=time.time())
    atomic_json(directory(home,task_id)/(note['note_id']+'.json'),note)
    return note


def pending(home, task_id, state):
    delivered=set(state.get('operator_notes_delivered',[]))
    values=[]
    for path in directory(home,task_id).glob('*.json'):
        value=json.loads(path.read_text())
        if value['task_id']!=task_id:raise ValueError('Operator inbox task differs')
        if value['note_id'] not in delivered:values.append(value)
    return sorted(values,key=lambda n:(n['created'],n['note_id']))
