"""Bounded native inference endpoint probe; never an AI4Research task score.

Run on an authorized inference host over SSH. Catalog inspection is read-only;
--generate explicitly permits two small sequential generation requests.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import stat
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def probe(base_url,model,*,generate=False,token_file=None):
    url=urlsplit(base_url)
    if (url.scheme not in {"http","https"} or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.scheme == "http" and url.hostname not in {"127.0.0.1","localhost","::1"}):
        raise ValueError("credential-free HTTPS endpoint or same-host HTTP loopback required")
    headers={"Content-Type":"application/json"}
    opener=build_opener(ProxyHandler({}),NoRedirect())
    if token_file:
        path=Path(token_file)
        meta=path.stat()
        if (any(p.is_symlink() for p in (path,*path.parents)) or not stat.S_ISREG(meta.st_mode)
                or meta.st_nlink != 1 or meta.st_size > 16384
                or os.name == "posix" and (meta.st_uid != os.geteuid() or meta.st_mode & 0o077)):
            raise ValueError("bounded protected credential file required")
        token=path.read_text().strip()
        if not token or any(c in token for c in '\r\n\0'): raise ValueError("invalid protected credential")
        headers["Authorization"]="Bearer "+token
    result={"schema":"ai4r-native-inference-probe:1","checked_at":datetime.now(timezone.utc).isoformat(),
            "base_url":base_url,"requested_model":model,"scope":"endpoint capability smoke; no product benchmark score",
            "generations_authorized":generate,"requests":[],"cost":None}
    def request(name,path,payload=None):
        began=time.monotonic()
        row={"name":name,"status":"unavailable","request":payload}
        try:
            raw=None if payload is None else json.dumps(payload).encode()
            with opener.open(Request(base_url.rstrip("/")+path,data=raw,headers=headers),timeout=90) as response:
                data=response.read(512*1024+1)
                if len(data)>512*1024: raise ValueError("response exceeds finite probe bound")
                row.update(status="observed",http_status=response.status,response=json.loads(data))
        except HTTPError as error:
            row.update(status="rejected",http_status=error.code,error_type=type(error).__name__)
        except (URLError,TimeoutError,OSError,ValueError) as error:
            row.update(error_type=type(error).__name__,outcome_unknown=payload is not None)
        row["elapsed_s"]=time.monotonic()-began
        result["requests"].append(row)
        return row
    catalog=request("catalog","/models")
    ids=[x.get("id") for x in catalog.get("response",{}).get("data",[])]
    result["catalog_model_present"]=model in ids
    if not generate or not result["catalog_model_present"]:
        return result
    payload={"model":model,"temperature":0,"max_tokens":256,
             "chat_template_kwargs":{"enable_thinking":False},
             "messages":[{"role":"user","content":"Calculate 2 + 2. Return only a JSON object with exactly two fields: sum (an integer) and units (the string items). No prose or code fences."}]}
    schema={"type":"object","properties":{"sum":{"type":"integer"},"units":{"type":"string","enum":["items"]}},
            "required":["sum","units"],"additionalProperties":False}
    for name,body in (("prompt-json",payload),("native-json-schema",{**payload,"response_format":{
            "type":"json_schema","json_schema":{"name":"bounded_smoke","strict":True,"schema":schema}}})):
        row=request(name,"/chat/completions",body)
        value=row.get("response",{})
        choices=value.get("choices") or []
        if choices:
            row["effective_model"]=value.get("model")
            row["finish_reason"]=choices[0].get("finish_reason")
            try:
                parsed=json.loads(choices[0]["message"]["content"])
                row["limited_json_check_passed"]=(type(parsed.get("sum")) is int and parsed == {"sum":4,"units":"items"})
            except (ValueError,TypeError,KeyError,AttributeError):
                row["limited_json_check_passed"]=False
        if row.get("outcome_unknown"):
            break  # No automatic resend or second generation after uncertainty.
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",required=True)
    parser.add_argument("--model",required=True)
    parser.add_argument("--generate",action="store_true")
    parser.add_argument("--token-file")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if args.output and args.output.exists():
        raise ValueError("output must be new; no probe requests were sent")
    result=probe(args.base_url,args.model,generate=args.generate,token_file=args.token_file)
    raw=json.dumps(result,indent=2,allow_nan=False)+"\n"
    if args.output:
        with args.output.open("x",encoding="utf-8") as stream: stream.write(raw)
    else:
        print(raw,end="")
    return 0 if result["catalog_model_present"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
