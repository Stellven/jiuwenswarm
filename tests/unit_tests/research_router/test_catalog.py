from copy import deepcopy

import pytest

from jiuwenswarm.research_router.catalog import CatalogError, QualifiedCatalog, source_inventory


def entry(**overrides):
    value = {"model_id": "test.executor", "kind": "E", "enabled": True,
             'adapter_id':'native-openai-chat-v1','adapter_revision':'disposable:1','qualified_adapter_revision':'disposable:1',
             "qualification": "contract_qualified", "current": True,
             "deployment_ref": {"id": "deployment", "sha256": "a" * 64},
             "qualified_deployment_sha256": "a" * 64,
             "categories": ["software_systems_and_performance"],
             "capabilities": {"modalities": ["text"], "context_tokens": 8192,
                              "output_tokens": 1024, "tool_calling": False},
             "access_verified": True, "license_approved": True,
             "host_ready": True, "dependencies_ready": True,
             "provider": {"provider_id": "test", "base_url": "https://example.invalid/v1",
                          "models": [{"model_id": "test.executor", "provider_model_name": "test"}],
                          "credential_env_var": "TEST_PROVIDER_KEY", "timeout_s": 60, "enabled": True}}
    value.update(overrides)
    return value


def test_inventory_is_source_shortlist_never_enabled():
    rows = source_inventory()
    assert len(rows) == 24
    assert sum(x["kind"] == "E" for x in rows) == 12
    assert sum(x["kind"] == "T" for x in rows) == 12
    assert not any(x["enabled"] for x in rows)


@pytest.mark.parametrize("change,reason", [({"kind": "T"}, "NOT_EXECUTOR"),
    ({"enabled": False}, "DEPLOYMENT_BLOCKED"), ({"current": False}, "SERVICE_STALE"),
    ({"access_verified": False}, "MODEL_ACCESS_UNAVAILABLE"),
    ({"qualified_deployment_sha256": "b" * 64}, "SERVICE_STALE")])
def test_catalog_retains_specific_exclusions(change, reason):
    cat = QualifiedCatalog([entry(**change)])
    assert cat.candidates()[0] == []
    assert reason in cat.candidates()[1][0]["reason_codes"]


def test_catalog_rejects_credentials_or_invalid_provider_timeout():
    value = entry(); value["provider"]["api_key"] = "do-not-print"
    with pytest.raises(CatalogError, match="credential"):
        QualifiedCatalog([value])
    value = entry(); value["provider"]["timeout_s"] = 601
    with pytest.raises(CatalogError, match="timeout"):
        QualifiedCatalog([value])
    assert "do-not-print" not in str(CatalogError("credential value prohibited"))

