"""Write-once audience-filtered sample exports. No path back to live state."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import uuid
import tempfile


def safe_relative(path):
    if not isinstance(path,str) or not path or "\\" in path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
        raise ValueError("unsafe export path")
    return path


def export_label(run_id,node_id,attempt_id,subnode_id):
    key="/".join((run_id,node_id,attempt_id,subnode_id if subnode_id is not None else "-"))
    return "held_out" if int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8],16)%5==0 else "development"


def content_hash(files):
    if len({x["path"] for x in files}) != len(files): raise ValueError("duplicate export file")
    lines=[]
    for row in sorted(files,key=lambda x:x["path"].encode("utf-8")):
        safe_relative(row["path"])
        lines.append(row["path"]+"\t"+row["sha256"]+"\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def build_export(destination, records, records_bytes, *, bundles, read_file, file_rows, audience="development"):
    if audience not in {"development","referee"}: raise ValueError("unknown export audience")
    if not 1<=len(records)<=5000 or len({x["id"] for x in records})!=len(records): raise ValueError("invalid export population")
    output=Path(destination)
    if output.exists() or output.is_symlink():raise ValueError('export identity already published')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.partial-export-',dir=output.parent) as temporary:
        manifest=_build(Path(temporary),output.name,records,records_bytes,bundles=bundles,read_file=read_file,file_rows=file_rows,audience=audience)
        os.rename(temporary,output)
        return manifest


def _build(output,identity,records,records_bytes,*,bundles,read_file,file_rows,audience):
    raw_lines={}
    for line in records_bytes.splitlines(keepends=True):
        value=json.loads(line)
        if value['id'] in raw_lines:raise ValueError('duplicate raw record identity')
        raw_lines[value['id']]=(value,line)
    if any(r['id'] not in raw_lines or raw_lines[r['id']][0]!=r for r in records):raise ValueError('record population differs from exact source bytes')
    files=[];entries=[];omitted=[];redactions=[];selected=[]
    for record in records:
        label=export_label(record["run_id"],record["node_id"],record["attempt_id"],record.get("subnode_id"))
        if label=="held_out" and audience!="referee":
            omitted.append({'obligation_id':record['id'],'reason':'held_out audience denied','blocking':False});continue
        folder="calls/"+record["id"].replace(":","_")+"/"
        if "/" in record["id"] or "\\" in record["id"] or ".." in record["id"]:raise ValueError("unsafe observation identity")
        selected.append(record)
        entries.append({"observation_id":record["id"],**{k:record[k] for k in ("run_id","node_id","attempt_id","subnode_id","failure_class")},"call_folder":folder,"label":label})
        rows=file_rows.get(record["id"],[])
        # Each entry always includes the exact completed observation in its call folder.
        payload=raw_lines[record['id']][1]
        rows=[{"path":"observation.json","bytes_data":payload,"audiences":[audience]},*rows]
        for row in rows:
            if row.get("protected_evaluation") or audience not in row.get("audiences",["referee"]):
                redactions.append("protected or audience-restricted evidence omitted");continue
            data=row["bytes_data"] if "bytes_data" in row else read_file(row["ref"])
            if "ref" in row and hashlib.sha256(data).hexdigest()!=row["ref"]["sha256"]:raise ValueError("export source digest mismatch")
            name=folder+safe_relative(row["path"])
            if any(x['path']==name for x in files):raise ValueError('duplicate exported file path')
            target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("xb") as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            files.append({"path":name,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
    if not entries: raise ValueError("no exportable executions for audience")
    actual=b''.join(raw_lines[x['id']][1] for x in selected)
    (output/"records.jsonl").write_bytes(actual)
    files.append({"path":"records.jsonl","sha256":hashlib.sha256(actual).hexdigest(),"bytes":len(actual)})
    used_runs={x["run_id"] for x in entries}
    if not used_runs<=set(bundles):raise ValueError("every exported run needs its bundle")
    bundle_refs=[]
    for run in sorted(used_runs):
        ref=bundles[run];data=read_file(ref)
        if hashlib.sha256(data).hexdigest()!=ref["sha256"]:raise ValueError("bundle digest mismatch")
        name="bundles/"+hashlib.sha256(run.encode()).hexdigest()+".json";target=output/name;target.parent.mkdir(exist_ok=True)
        target.write_bytes(data);bundle_refs.append({"id":name,"sha256":ref["sha256"]})
        files.append({"path":name,"sha256":ref["sha256"],"bytes":len(data)})
    if len(files)>100000 or len(omitted)>100 or len(used_runs)>500:raise ValueError('export exceeds source representation bounds')
    manifest={"schema_version":"1.0.0","id":identity,"built_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "records_ref":{"id":"records.jsonl","sha256":hashlib.sha256(actual).hexdigest()},"bundle_refs":bundle_refs,
        "entries":entries,"files":files,"content_sha256":content_hash(files),"omitted":omitted,"redactions":sorted(set(redactions))}
    (output/"export.json").write_bytes(json.dumps(manifest,sort_keys=True,ensure_ascii=False,allow_nan=False).encode())
    return manifest

