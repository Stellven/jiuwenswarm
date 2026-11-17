"""Small, versioned data interconnect; execution remains native CC v2."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re

VERSION = 'factory.interconnect/1'
KINDS = {'json', 'text', 'artifact', 'handle'}
CHANNELS = {'outputs', 'result'}


@lru_cache(maxsize=1)
def contract_schema():
    return json.loads(Path(__file__).with_name('interconnect.schema.json').read_text(encoding='utf-8'))


def check_reference(channel='outputs', pointer='', kind=None):
    if not isinstance(channel, str) or channel not in CHANNELS:
        raise ValueError('Interconnect channel must be outputs or result')
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')) or re.search(r'~(?![01])', pointer):
        raise ValueError('Interconnect pointer must be an RFC 6901 JSON Pointer')
    if (pointer or channel != 'outputs') and kind is not None and (not isinstance(kind, str) or kind not in KINDS):
        raise ValueError('Unknown interconnect value kind')
    if pointer and kind is None:
        raise ValueError('A field selection must declare its resulting kind')


def select(value, pointer=''):
    """Copy a value or select a JSON field. No expressions, code or coercions."""
    check_reference(pointer=pointer, kind='json')
    for token in pointer.split('/')[1:] if pointer else ():
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list) and re.fullmatch(r'0|[1-9][0-9]*', token) and int(token) < len(value):
            value = value[int(token)]
        else:
            raise ValueError('Interconnect field does not exist: ' + pointer)
    return deepcopy(value)


def check_assembly(assembly):
    if assembly is None:
        return
    if not isinstance(assembly, dict) or set(assembly) != {'template', 'at'} or not isinstance(assembly['template'], dict):
        raise ValueError('Assembly requires an object template and an insertion pointer')
    check_reference(pointer=assembly['at'], kind='json')
    if not assembly['at']:
        raise ValueError('Assembly insertion must name a field')


def assemble(value, assembly=None):
    if assembly is None:
        return value
    check_assembly(assembly)
    result = deepcopy(assembly['template'])
    tokens = [t.replace('~1', '/').replace('~0', '~') for t in assembly['at'].split('/')[1:]]
    current = result
    for index, token in enumerate(tokens):
        last = index == len(tokens) - 1
        if isinstance(current, dict) and (last or token in current):
            if last:
                current[token] = deepcopy(value)
            else:
                current = current[token]
        elif isinstance(current, list) and re.fullmatch(r'0|[1-9][0-9]*', token) and int(token) < len(current):
            if last:
                current[int(token)] = deepcopy(value)
            else:
                current = current[int(token)]
        else:
            raise ValueError('Assembly insertion parent does not exist')
    return result


class Ports(dict):
    """Ordinary output ports plus the separately declared completion channel."""
    def __init__(self, outputs, result=None):
        super().__init__(outputs)
        self.result = result or {}
