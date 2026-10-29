"""One release table for every stage that has selectable versions.

A release is selected by name through protected settings. This table is the only
place that says which names exist, what an absent selection historically means,
what a new capture selects, and how a selected release changes the static
template. Bootstrap, profile capture and static-template capture all read it, so
a new release is added here and nowhere else. Unknown names fail loudly.
"""
from __future__ import annotations

import copy

from .contracts import ResearchError
from .state import json_bytes

# implicit: what an absent selection means in an already captured profile. It never
#   changes, so historical profiles and their pinned static templates stay valid.
# capture_default: what a new capture selects when the operator names nothing.
# source: which prepared asset set carries the stage declaration at bootstrap.
# versions: name -> facts. 'template' is None when the release adds no static
#   pipeline node (it is installed for planning and direct use only), or the name
#   of the static-template rewrite that adopts it.
RELEASES = {
    'intent': {'implicit': 'm1-6', 'capture_default': 'm1-8', 'source': 'compiler', 'label': 'Intent',
               'versions': {'m1-6': {}, 'm1-7': {'compiler_time_s': 900}, 'm1-8': {'compiler_time_s': 900}}},
    'requirements': {'implicit': 'm1-8', 'capture_default': 'm1-8', 'source': 'compiler', 'label': 'Requirements',
                     'versions': {'m1-8': {}, 'm1-9': {}}},
    'screening': {'implicit': 'm1-4', 'capture_default': 'm1-4', 'source': 'research', 'label': 'Screening',
                  # m1-6 has its own input and output contracts: it is not a drop-in for the
                  # fixed three-dimension pipeline, so the static template keeps its node.
                  'versions': {'m1-4': {}, 'm1-5': {'template': 'pin'}, 'm1-6': {'template': None}}},
    'delivery': {'implicit': 'm1-5', 'capture_default': 'm1-5', 'source': 'research', 'label': 'Delivery',
                 'versions': {'m1-5': {}, 'm1-6': {'template': 'delivery_evidence'}}},
}
STAGES = tuple(RELEASES)


def release_names(stage):
    return tuple(RELEASES[stage]['versions'])


def require_release(stage, version, code):
    """Return version when it names a known release of stage; otherwise raise loudly."""
    row = RELEASES[stage]
    if not isinstance(version, str) or version not in row['versions']:
        raise ResearchError(code, 'Unsupported explicit %s release' % row['label'],
                            {'stage': stage, 'known': list(row['versions'])})
    return version


def implicit_release(stage):
    return RELEASES[stage]['implicit']


def capture_default(stage):
    return RELEASES[stage]['capture_default']


def release_facts(stage, version):
    return RELEASES[stage]['versions'][version]


def pinned_extras(selections, compiler_assets, research_assets):
    """Declaration hashes of every non-implicit selected release, in stage order."""
    pins = ()
    for stage in STAGES:
        row = RELEASES[stage]
        if selections[stage] != row['implicit']:
            assets = compiler_assets if row['source'] == 'compiler' else research_assets
            pins += (assets[stage]['declaration_ref']['sha256'],)
    return pins


def release_options_from_environment(environ):
    """capture_local_profile keywords from protected settings JIUWENSWARM_M1_<STAGE>_VERSION.

    A setting that is absent is left out, so the capture default (or what an existing
    profile froze) applies. A setting that is present is passed on and checked there.
    """
    names = {stage: 'JIUWENSWARM_M1_%s_VERSION' % stage.upper() for stage in STAGES}
    return {stage + '_version': environ[name] for stage, name in names.items() if name in environ}


def _delivery_evidence(node):
    """Delivery m1-6 takes one typed evidence bundle and writes only the report."""
    node['inputs'] = [{'accepted_ref': None, 'artifact_type': 'delivery_evidence_bundle', 'future': None,
                       'name': 'evidence_bundle', 'required': True, 'run_input_key': 'evidence_bundle',
                       'source_kind': 'accepted_ref'}]
    node['outputs'] = [row for row in node['outputs'] if row['name'] == 'research_report']
    return node


_REWRITES = {'pin': lambda node: node, 'delivery_evidence': _delivery_evidence}


def apply_template_releases(store, raw, selections, code):
    """Return the static template blob for the selections.

    Historical bytes are returned unchanged when nothing needs a node rewrite, so
    existing profiles keep the same template identity.
    """
    import json
    from .capsules.assets import build_research_assets
    for stage in STAGES:
        require_release(stage, selections[stage], code)
    rewrites = [(stage, selections[stage]) for stage in STAGES
                if selections[stage] != RELEASES[stage]['implicit']
                and RELEASES[stage]['versions'][selections[stage]].get('template') is not None]
    if not rewrites:
        return store.put_blob(raw, media_type='application/json')
    template = json.loads(raw)
    for stage, version in rewrites:
        row = RELEASES[stage]
        asset = build_research_assets(store, **{stage + '_version': version})[stage]
        declaration = store.read_record(asset['declaration_ref'])
        matches = [node for node in template['nodes'] if node['node_id'] == stage]
        if len(matches) != 1 or matches[0]['cc']['cc_version'] != row['implicit']:
            raise ResearchError(code, 'Installed static %s base is not exact %s' % (row['label'], row['implicit']))
        node = matches[0]
        node['cc'] = {'cc_name': declaration['identity']['name'], 'cc_version': version,
                      'declaration_sha256': asset['declaration_ref']['sha256']}
        _REWRITES[row['versions'][version]['template']](node)
    # Template ids are at most 64 characters; several selections use the short form.
    full = template['id'] + ''.join('.%s-%s' % pair for pair in rewrites)
    template['id'] = full if len(full) <= 64 else template['id'] + ''.join('.%s%s' % (stage[:3], version[3:]) for stage, version in rewrites)
    template['template_name'] = 'm1_' + '_'.join('%s_%s' % (stage, version.replace('-', '_')) for stage, version in rewrites)
    return store.put_blob(json_bytes(template), media_type='application/json')
