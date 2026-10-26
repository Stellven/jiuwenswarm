import importlib.metadata,json,os,pathlib,platform,socket
meta=json.loads(pathlib.Path('inputs/runtime-meta.json').read_text())
versions={}
for name in ('httpx','jsonschema','psutil','numpy','scikit-learn','torch'):
 try: versions[name]=importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError: versions[name]=None
record=dict(meta,runner_hostname=socket.gethostname(),runner_os=platform.platform(),
 runner_architecture=platform.machine(),runner_python=platform.python_version(),
 runner_uid=os.getuid(),runner_package_versions=versions)
pathlib.Path('runtime-environment.json').write_text(json.dumps(record,indent=2))
print(json.dumps({'runtime_environment':'runtime-environment.json','host':meta['physical_host'],
 'checkout_commit':meta['checkout_commit'],'app_build_id':meta['app_build_id']}))
