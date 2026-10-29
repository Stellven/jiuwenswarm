"""Immutable utility-RSI scope derived from the captured denial template."""
from .contracts import ResearchError

SCOPE = {'schema': 'ai4r-utility-rsi-scope:1',
         'targets': ['utility.calculate', 'utility.table_normalize'],
         'work_stages': ['intent', 'verifier'], 'setup_model_calls': 12,
         'rsi_model_calls_per_target': 10, 'product_eligible': False}


def require_scope(store, operator, protected_options):
    template = store.read_record(operator['cc']['static_template_ref'])
    scoped = isinstance(template, dict) and template.get('schema') == 'ai4r-utility-rsi-no-product-template:1'
    marker = protected_options.get('utility_rsi_scope')
    if scoped:
        if template.get('scope') != SCOPE or template.get('product_execution') != 'forbidden' or marker != SCOPE:
            raise ResearchError('utility_rsi_scope', 'Captured utility-only scope must be preserved exactly')
        return SCOPE
    if marker is not None:
        raise ResearchError('utility_rsi_scope', 'Utility scope must come from its immutable denial template')
    return None
