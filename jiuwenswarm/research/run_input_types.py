"""Real artifact types of host-supplied run inputs.

Host capture, not the Planner or a Capsule, says what supplied bytes are. The
binder compares this type with the consumer port, so a plan cannot feed a paper
summary to a work-packet port by naming the input key.
"""
from __future__ import annotations

# resource_key -> (artifact_type, schema_ref). A None schema_ref checks the type
# only: the Brief schema version is a property of the run's own Brief record and
# differs between consumer releases.
RUN_INPUT_TYPES = {
    'brief': ('research_brief', None),
    'search_scope': ('search_scope', 'search-scope:field-contract:1'),
    'baseline_resource': ('resource_snapshot', 'resource-snapshot:field-contract:1'),
    'validation_resource': ('resource_snapshot', 'resource-snapshot:field-contract:1'),
    'environment_lock': ('environment_lock', 'environment-lock:field-contract:1'),
    'local_document_buffer': ('local_document_buffer', 'urn:ai4r:paper-document-buffer:1.0.0'),
    'original_request': ('original_request', 'opaque-bytes'),
}


def typed_resource(item):
    """Return an inventory item with the host-known type of its resource key."""
    known = RUN_INPUT_TYPES.get(item['resource_key'])
    if known is None:
        return item
    result = dict(item, artifact_type=known[0])
    if known[1] is not None:
        result['schema_ref'] = known[1]
    return result


def supplied_type(resource_key, resource_map):
    """Return (artifact_type, schema_ref) of an accepted_ref input, or None when untyped."""
    if resource_key in ('brief', 'search_scope'):
        return RUN_INPUT_TYPES[resource_key]
    item = resource_map.get(resource_key)
    if item is None or item.get('artifact_type') is None:
        return None
    return item['artifact_type'], item.get('schema_ref')
