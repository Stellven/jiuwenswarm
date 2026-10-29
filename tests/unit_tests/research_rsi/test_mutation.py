import pytest
from jiuwenswarm.research_rsi.mutation import checked_changes,SecurityViolation


def test_exact_allowed_single_body_and_no_links(tmp_path):
    root=tmp_path/'parent';root.mkdir();(root/'body.py').write_text('x=1\n')
    assert checked_changes(root,{'body.py':b'x=2\n'},['body.py'],[])==['body.py']
    for path in ['../body.py','/body.py','declaration.yaml','body.py/../../x']:
        with pytest.raises(SecurityViolation):checked_changes(root,{path:b'x'},['body.py'],[])
    with pytest.raises(SecurityViolation):checked_changes(root,{'body.py':b'x'},['body.py'],['body.py'])
