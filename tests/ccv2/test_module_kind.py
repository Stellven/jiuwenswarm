"""A capsule packages functional modules; each capability/material may declare its kind."""
import copy
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
    ccv2.normalize(copy.deepcopy(BASE))
    validate('cc.schema.json', copy.deepcopy(BASE))


@pytest.mark.parametrize('where,value', [('materials', 'tool'), ('materials', 'widget'), ('capabilities', 'skill')])
def test_wrong_kind_rejected(where, value):
    raw = copy.deepcopy(BASE)
    entry = next(iter(raw[where].values()))
    entry['kind'] = value
    with pytest.raises(ccv2.CCError):
        ccv2.normalize(raw)


def test_every_factory_module_declares_its_kind():
    root = Path(components.__file__).parent / 'ccs'
    for path in root.glob('**/cc.yaml'):
        decl = yaml.safe_load(path.read_text())
        ccv2.normalize(copy.deepcopy(decl))
        for name, cap in (decl.get('capabilities') or {}).items():
            assert cap.get('kind') == 'tool', (path, name)
        for name, material in (decl.get('materials') or {}).items():
            assert material.get('kind') in ccv2.MATERIAL_KINDS, (path, name)


def test_factory_refuses_component_without_component_kind(tmp_path, monkeypatch):
    folder = tmp_path / 'fake'
    folder.mkdir()
    (folder / 'component.yaml').write_text('depends_on: []\n')
    (folder / 'cc.yaml').write_text(yaml.safe_dump({'materials': {'component': {'path': 'component.yaml', 'kind': 'method'}}}))
    monkeypatch.setattr(components, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='Not a component module'):
        components.load('fake')
