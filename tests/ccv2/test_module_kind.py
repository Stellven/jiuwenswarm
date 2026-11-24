"""A capsule packages functional modules; each capability/material may declare its kind."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from jiuwenswarm.ccv2 import ccv2
from jiuwenswarm.ccv2.schema_tools import validate
from jiuwenswarm.factory import components

BASE = {'cc': '2', 'id': 'x.capsule', 'version': '1.0.0',
        'bindings': {'default': {'kind': 'native', 'command': ['true']}},
        'capabilities': {'run': {'does': 'Run it.', 'kind': 'tool'}},
        'materials': {'how': {'path': 'HOW.md', 'kind': 'skill'},
                      'judge': {'path': 'JUDGE.md', 'kind': 'method'},
                      'part': {'path': 'part.patch', 'kind': 'component'},
                      'notes': {'path': 'NOTES.md'}}}


def test_kinds_accepted_by_parser_and_schema():
    ccv2.normalize(copy.deepcopy(BASE), legacy=True)
    validate('cc.schema.json', copy.deepcopy(BASE))


@pytest.mark.parametrize('where,value', [('materials', 'tool'), ('materials', 'widget'), ('capabilities', 'skill')])
def test_wrong_kind_rejected(where, value):
    raw = copy.deepcopy(BASE)
    entry = next(iter(raw[where].values()))
    entry['kind'] = value
    with pytest.raises(ccv2.CCError):
        ccv2.normalize(raw)


def test_every_factory_module_declares_passive_roles():
    root = Path(components.__file__).parent / 'ccs'
    for path in root.glob('**/cc.yaml'):
        decl = yaml.safe_load(path.read_text())
        ccv2.normalize(copy.deepcopy(decl))
        from jiuwenswarm.ccv2.roles import read_roles
        roles=read_roles(decl,path.parent)
        for name, cap in (decl.get('capabilities') or {}).items():
            assert 'kind' not in cap and roles['capabilities'].get(name)=='tool', (path,name)
        for name, material in (decl.get('materials') or {}).items():
            assert 'kind' not in material and roles['materials'].get(name,'reference') in ccv2.MATERIAL_KINDS, (path,name)


def test_factory_refuses_component_without_component_kind(tmp_path, monkeypatch):
    folder = tmp_path / 'fake'
    folder.mkdir()
    (folder / 'component.yaml').write_text('depends_on: []\n')
    # A valid CC whose passive roles material declares the component as a method.
    (folder / 'roles.json').write_text(json.dumps({'format': 'factory-roles/1', 'capabilities': {},
                                                   'materials': {'component': 'method'}}))
    (folder / 'cc.yaml').write_text(yaml.safe_dump({
        'cc': '2', 'id': 'factory.components.fake', 'version': '1.0.0',
        'materials': {'component': {'path': 'component.yaml'},
                      'roles': {'path': 'roles.json', 'media_type': 'application/json'}}}))
    monkeypatch.setattr(components, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='not declared as a component'):
        components.load('fake')
