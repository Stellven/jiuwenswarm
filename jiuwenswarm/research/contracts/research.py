"""M1-IF-005@r1 adapters. The neutral source-pinned catalog owns JSON fields."""
from . import validate
from ..science import validate_empirical


def validate_research(contract_id, value, *, metric_ids=None, receipt_sequences=None):
    validate(contract_id, value)
    if contract_id in {'empirical-results', 'empirical-results:field-contract:2'}:
        if metric_ids is None or receipt_sequences is None:
            raise ValueError('C002 semantic checking requires frozen metrics and actual receipts')
        validate_empirical(value['runs'], metric_ids, receipt_sequences)
