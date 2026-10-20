"""Only finite resources explicitly owned by this job may be removed."""


def cleanup_plan(manifest,observed):
    if not manifest['project'].startswith(('ai4r-qa-','ai4r-verify-')):raise ValueError('standing project cleanup denied')
    result=[]
    for resource in manifest['resources']:
        if not resource['disposable']:continue
        if resource['kind'] not in {'container','network','scratch'}:raise ValueError('data volumes are retained')
        identity=observed.get(resource['id'])
        if identity!={'job_id':manifest['job_id'],'project':manifest['project']}:raise ValueError('foreign resource cleanup denied')
        result.append({'kind':resource['kind'],'id':resource['id']})
    return result
