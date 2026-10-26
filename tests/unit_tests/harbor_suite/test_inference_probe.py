"""Endpoint probes preserve uncertainty; test responses are synthetic only."""
import json
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from benchmarks.harbor_suite import inference_probe as p


class Response:
    status=200
    def __init__(self,value): self.raw=json.dumps(value).encode()
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,limit): return self.raw[:limit]


def test_catalog_only_never_generates(monkeypatch):
    requests=[]
    def opened(request,**kwargs):
        requests.append(request)
        return Response({"data":[{"id":"unit-model"}]})
    monkeypatch.setattr(p,"build_opener",lambda *args:SimpleNamespace(open=opened))
    result=p.probe("http://127.0.0.1:8000/v1","unit-model")
    assert result["catalog_model_present"] and len(requests)==1 and requests[0].data is None


def test_uncertain_generation_does_not_retry_or_send_second_probe(monkeypatch):
    requests=[]
    def opened(request,**kwargs):
        requests.append(request)
        if len(requests)==1: return Response({"data":[{"id":"unit-model"}]})
        raise URLError("unit uncertain transport")
    monkeypatch.setattr(p,"build_opener",lambda *args:SimpleNamespace(open=opened))
    result=p.probe("http://127.0.0.1:8000/v1","unit-model",generate=True)
    assert len(requests)==2 and result["requests"][-1]["outcome_unknown"]
    assert "unit uncertain transport" not in json.dumps(result)


def test_probe_rejects_unapproved_cleartext_or_embedded_credentials():
    for url in ("http://example.com/v1","https://user:secret@example.com/v1","https://example.com/v1?token=secret"):
        with pytest.raises(ValueError): p.probe(url,"unit-model")
    assert p.NoRedirect().redirect_request(None,None,None,None,None,None) is None
