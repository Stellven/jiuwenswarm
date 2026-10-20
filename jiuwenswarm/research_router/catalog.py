"""Read-only deployment metadata; registration confers no endpoint access."""
from copy import deepcopy
from urllib.parse import urlsplit


class CatalogError(ValueError):
    pass


INVENTORY = (
    ("E", "qwen.multimodal4b", "Qwen/Qwen3.5-4B"),
    ("E", "openai.economy", "gpt-6-luna"), ("E", "glm.general", "glm-5"),
    ("E", "deepseek.reasoning", "deepseek-v4-pro"),
    ("E", "math.kimina17b", "AI-MO/Kimina-Prover-RL-1.7B"),
    ("E", "math.goedel8b", "Goedel-LM/Goedel-Prover-V2-8B"),
    ("E", "qwen.code30b", "Qwen/Qwen3-Coder-30B-A3B-Instruct"),
    ("E", "code.devstral24b", "mistralai/Devstral-Small-2-24B-Instruct-2512"),
    ("E", "code.opencodereasoning7b", "nvidia/OpenCodeReasoning-Nemotron-1.1-7B"),
    ("E", "openai.general", "gpt-6.1-sol"), ("E", "anthropic.fable5", "claude-fable-5"),
    ("E", "gemini.research", "gemini-3.8-flash"),
    ("T", "vision.dinov2small", "facebook/dinov2-small"),
    ("T", "vision.sam21tiny", "facebook/sam2.1-hiera-tiny"),
    ("T", "evidence.docling258m", "ibm-granite/granite-docling-258M"),
    ("T", "evidence.paddleocr09b", "PaddlePaddle/PaddleOCR-VL-1.6"),
    ("T", "evidence.bgem3", "BAAI/bge-m3"),
    ("T", "evidence.qwenrerank06b", "Qwen/Qwen3-Reranker-0.6B"),
    ("T", "evidence.qwenembed06b", "Qwen/Qwen3-Embedding-0.6B"),
    ("T", "network.routenet_fermi", "RouteNet-Fermi"),
    ("T", "network.routenet_gauss", "RouteNet-Gauss"),
    ("T", "statistics.chronos2", "amazon/chronos-2"),
    ("T", "statistics.timesfm", "google/timesfm-2.5-200m-pytorch"),
    ("T", "statistics.moment", "AutonLab/MOMENT-1-small"),
)


def source_inventory():
    return [{"kind": kind, "model_id": name, "artifact": artifact,
             "enabled": False, "qualification": "unmeasured",
             "source": "M1-IF-008@r1/model-catalog.md"} for kind, name, artifact in INVENTORY]


def reject_credentials(value):
    """Reject secret-bearing fields without including their values in errors."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"api_key", "access_token", "password", "secret", "credential_value", "authorization"}:
                raise CatalogError("credential value prohibited")
            reject_credentials(child)
    elif isinstance(value, list):
        for child in value:
            reject_credentials(child)


class QualifiedCatalog:
    def __init__(self, entries):
        reject_credentials(entries)
        self.entries = deepcopy(entries)
        seen = set()
        for item in self.entries:
            if item.get("model_id") in seen or not item.get("model_id"):
                raise CatalogError("duplicate or missing model identity")
            seen.add(item["model_id"])
            provider = item.get("provider")
            if provider:
                timeout = provider.get("timeout_s")
                if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 600:
                    raise CatalogError("provider timeout outside 1-600 seconds")
                url = urlsplit(provider.get("base_url", ""))
                if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                    raise CatalogError("provider endpoint must be credential-free HTTPS")

    def candidates(self):
        eligible, excluded = [], []
        for item in self.entries:
            reasons = []
            if item.get("kind") != "E": reasons.append("NOT_EXECUTOR")
            if not item.get("enabled"): reasons.append("DEPLOYMENT_BLOCKED")
            if not item.get("access_verified"): reasons.append("MODEL_ACCESS_UNAVAILABLE")
            if not item.get("license_approved"): reasons.append("POLICY_DENIED")
            if item.get("qualification") not in {"contract_qualified", "development_profiled", "benchmark_profile_frozen"}:
                reasons.append("CAPABILITY_UNVERIFIED")
            if item.get('adapter_id')!='native-openai-chat-v1' or not item.get('adapter_revision') or item.get('qualified_adapter_revision')!=item.get('adapter_revision'):
                reasons.append('CAPABILITY_UNVERIFIED')
            if not item.get("current") or item.get("qualified_deployment_sha256") != item.get("deployment_ref", {}).get("sha256"):
                reasons.append("SERVICE_STALE")
            if not item.get("host_ready") or not item.get("dependencies_ready"): reasons.append("ENVIRONMENT_BLOCKED")
            if reasons: excluded.append({"model_id": item["model_id"], "reason_codes": reasons})
            else: eligible.append(deepcopy(item))
        return eligible, excluded

