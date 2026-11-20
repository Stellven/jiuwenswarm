"""Non-executing normalization of workflow definitions and CC v2 declarations.

This draft is a declaration interface, not an executor, authority grant or
claim of algorithm/backend compatibility. Original declarations are retained.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

SCHEMA = Path(__file__).parent / 'schemas/capability-pool.schema.json'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def reference(entry):
    return {'id': entry['id'], 'version': entry['version']}


def _entry(identifier, name, kind, declaration, origin, version=None):
    return {'id': identifier, 'version': version or 'sha256:' + digest(declaration),
            'name': name, 'kind': kind, 'inputs': {}, 'outputs': {},
            'requirements': {'resources': [], 'effects': None, 'backends': None,
                             'constraints': {}}, 'verification': [],
            'origin': {**deepcopy(origin), 'declaration_sha256': digest(declaration),
                       'original': deepcopy(declaration)}}


def _workflow_port(kind):
    return {'transport': 'artifact', 'semantic_type': kind, 'required': True,
            'data_schema': {}, 'schema_known': False}


def normalize_workflows(library, catalog, origin):
    """Accept the existing registry export and serialized executable catalog."""
    entries, stages, subs = [], {}, {}
    for stage in catalog['stages']:
        e = _entry('workflow:stage/' + stage['id'], stage['name'], 'operation', stage, origin)
        e['origin']['path'] = 'jiuwenswarm/software_factory/catalog.py'
        for side in ('inputs', 'outputs'):
            e[side] = {p['name']: _workflow_port(p['kind']) for p in stage[side]}
        e['implementation'] = {'type': 'python', 'entrypoint': stage['entrypoint']}
        if stage.get('validation_bindings'):
            e['implementation']['validators'] = deepcopy(stage['validation_bindings'])
        e['requirements'] = {
            'resources': [{'category': category, 'name': value}
                          for key, category in (('tools', 'tool'), ('environment', 'environment'))
                          for value in stage.get(key, [])],
            'effects': None, 'backends': stage.get('backends') or None,
            'constraints': deepcopy(stage.get('accepts', {}))}
        e['verification'] = [stage['verifier']]
        stages[stage['id']] = e
        entries.append(e)

    def composite(definition, identifier, children, targets):
        e = _entry(identifier, definition['name'], 'composite', definition, origin)
        e['inputs'] = {name: _workflow_port(kind) for name, kind in definition['inputs'].items()}
        nodes = []
        by_alias = {}
        for child in children:
            target = targets[child.get('stage_id', child.get('definition'))]
            by_alias[child['id']] = target
            nodes.append({'id': child['id'], 'capability': reference(target),
                          'bindings': {port: {'node': binding['source'], 'port': binding['port']}
                                       for port, binding in child['bindings'].items()}})
        exposed = {}
        for name, binding in definition['outputs'].items():
            port = (e['inputs'] if binding['source'] == '$input' else
                    by_alias[binding['source']]['outputs'])[binding['port']]
            e['outputs'][name] = deepcopy(port)
            exposed[name] = {'node': binding['source'], 'port': binding['port']}
        e['composition'] = {'nodes': nodes, 'outputs': exposed}
        return e

    for sub in library['subworkflows']:
        e = composite(sub, 'workflow:subworkflow/' + sub['id'], sub['stages'], stages)
        subs[sub['id']] = e
        entries.append(e)
    for workflow in library['workflows']:
        entries.append(composite(workflow, 'workflow:workflow/' + workflow['id'],
                                 workflow['subworkflows'], subs))
    return entries


def _cc_port(spec, definitions):
    seen = set()
    while isinstance(spec, str) and spec.startswith('$'):
        name = spec[1:]
        if name in seen or name not in definitions:
            raise ValueError('Missing or cyclic CC port definition: ' + name)
        seen.add(name)
        spec = definitions[name]
    spec = {'kind': spec} if isinstance(spec, str) else deepcopy(spec)
    kind = spec['kind']
    if kind not in {'json', 'text', 'artifact', 'handle'}:
        raise ValueError('Unknown CC port kind: ' + str(kind))
    result = {'transport': kind if kind in {'artifact', 'handle'} else 'value',
              'semantic_type': 'cc:' + kind, 'required': not spec.get('optional', False),
              'data_schema': spec.get('schema', {'type': 'string'} if kind == 'text' else {}),
              'schema_known': 'schema' in spec or kind == 'text'}
    for name in ('description', 'media_type'):
        if name in spec:
            result[name] = spec[name]
    return result


def normalize_cc(cc, origin, read_material):
    """read_material(relative_path) returns actual bytes from a pinned bundle.

    Bindings remain declarations: no shell, tool, service or donor module runs.
    """
    if cc.get('cc') != '2':
        raise ValueError('Only CC v2 is supported')
    parent = _entry('cc:' + cc['id'], cc['id'], 'collection', cc, origin, cc['version'])
    entries, members = [parent], []
    for name, declaration in cc.get('capabilities', {}).items():
        binding_name = declaration.get('using', 'default')
        if binding_name not in cc.get('bindings', {}):
            raise ValueError('Missing CC execution binding: ' + binding_name)
        e = _entry(parent['id'] + '/tool/' + name, name, 'operation', declaration,
                   origin, cc['version'])
        e['description'] = declaration['does']
        for target, source in (('inputs', 'takes'), ('outputs', 'gives')):
            e[target] = {key: _cc_port(value, cc.get('defs', {}))
                         for key, value in declaration.get(source, {}).items()}
        e['implementation'] = {'type': 'cc', 'bundle': reference(parent), 'capability': name,
                               'binding': deepcopy(cc['bindings'][binding_name])}
        if 'serves' in declaration:
            e['implementation']['serves'] = deepcopy(declaration['serves'])
        e['requirements'] = {
            'resources': [{'category': 'unspecified', 'name': name}
                          for name in declaration.get('needs', [])],
            'effects': deepcopy(declaration.get('changes')),
            'backends': None, 'constraints': {}}
        e['verification'] = deepcopy(declaration.get('guarantees', []))
        entries.append(e)
        members.append(reference(e))
    for name, declaration in cc.get('materials', {}).items():
        from pathlib import PurePosixPath
        path = declaration['path']
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or '..' in parsed.parts or '\\' in path or ':' in path:
            raise ValueError('Material must stay inside its source bundle')
        raw = read_material(path)
        e = _entry(parent['id'] + '/material/' + name, name, 'material', declaration,
                   origin, cc['version'])
        e['material'] = {'path': path, 'role': declaration.get('kind', 'unspecified'),
                          'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
        entries.append(e)
        members.append(reference(e))
    if not members:
        raise ValueError('Empty CC container')
    parent['members'] = members
    return entries


def validate_pool(pool):
    """Validate structure, closed references, port wiring and composition DAGs.

    Passing this check does not validate files, computation or execution grants.
    """
    from jsonschema import Draft202012Validator
    Draft202012Validator(json.loads(SCHEMA.read_text())).validate(pool)
    entries = {}
    for e in pool['entries']:
        key = (e['id'], e['version'])
        if key in entries:
            raise ValueError('Duplicate capability identity: ' + e['id'])
        if e['origin']['declaration_sha256'] != digest(e['origin']['original']):
            raise ValueError('Original declaration hash mismatch')
        entries[key] = e
    def resolve(ref):
        key = (ref['id'], ref['version'])
        if key not in entries:
            raise ValueError('Unknown pinned capability: ' + ref['id'])
        return entries[key]
    graph = {}
    for key, e in entries.items():
        graph[key] = []
        if e['kind'] == 'collection':
            for ref in e['members']:
                resolve(ref)
        if e['kind'] == 'operation' and e['implementation']['type'] == 'cc':
            if resolve(e['implementation']['bundle'])['kind'] != 'collection':
                raise ValueError('CC binding requires a collection')
        if e['kind'] != 'composite':
            continue
        available = {'$input': e['inputs']}
        for node in e['composition']['nodes']:
            if node['id'] in available:
                raise ValueError('Duplicate or reserved node alias')
            target = resolve(node['capability'])
            if target['kind'] not in {'operation', 'composite'}:
                raise ValueError('Material/collection is not executable')
            graph[key].append((target['id'], target['version']))
            required = {name for name, port in target['inputs'].items() if port['required']}
            if not required <= node['bindings'].keys() or node['bindings'].keys() - target['inputs'].keys():
                raise ValueError('Missing or unknown input binding')
            for name, binding in node['bindings'].items():
                if binding['node'] not in available or binding['port'] not in available[binding['node']]:
                    raise ValueError('Unknown or forward port binding')
                supplied = available[binding['node']][binding['port']]
                needed = target['inputs'][name]
                if needed['required'] and not supplied['required']:
                    raise ValueError('Optional output cannot guarantee a required input')
                if any(supplied[field] != needed[field] for field in ('transport', 'semantic_type')):
                    raise ValueError('Incompatible transport/semantic type; requires an executable adapter')
            available[node['id']] = target['outputs']
        if set(e['composition']['outputs']) != set(e['outputs']):
            raise ValueError('Exposed outputs must match output ports')
        for name, binding in e['composition']['outputs'].items():
            if binding['node'] not in available or binding['port'] not in available[binding['node']]:
                raise ValueError('Unknown exposed output')
            if available[binding['node']][binding['port']] != e['outputs'][name]:
                raise ValueError('Exposed output contract mismatch')
    visiting, done = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError('Recursive composite cycle')
        if key in done:
            return
        visiting.add(key)
        for child in graph[key]:
            visit(child)
        visiting.remove(key)
        done.add(key)
    for key in graph:
        visit(key)
    return pool
