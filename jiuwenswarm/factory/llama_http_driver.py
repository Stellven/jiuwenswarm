"""Owned in-container HTTP driver. Raw SSE and client clock observations, no scoring."""
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import sys
import time


def emit(value):
    print(json.dumps(value,separators=(',',':')),flush=True)


def main():
    contract=json.loads(Path(sys.argv[1]).read_text())
    work=contract['workload']
    executable='/opt/llamacpp/llama-server'
    with open(executable,'rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    command=[executable,*work['argv'],'--host','127.0.0.1','--port','18080']
    emit(dict(event='launch',argv=command,executable_sha256=digest))
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=sys.stderr,stderr=sys.stderr)
    def request(path,body=None,timeout=5):
        conn=http.client.HTTPConnection('127.0.0.1',18080,timeout=timeout)
        conn.request('GET' if body is None else 'POST',path,body=None if body is None else json.dumps(body),headers={'Content-Type':'application/json'})
        return conn,conn.getresponse()
    try:
        deadline=time.monotonic()+min(480,contract['limits']['timeout_s']-30)
        while True:
            if process.poll() is not None:raise RuntimeError('Server exited before ready: '+str(process.returncode))
            try:
                conn,response=request('/health');data=response.read(65537);status=response.status;conn.close()
                if status==200:
                    emit(dict(event='ready',endpoint='http://127.0.0.1:18080/health',status=status,body=data.decode()));break
            except (OSError,http.client.HTTPException):pass
            if time.monotonic()>deadline:raise TimeoutError('Server readiness deadline')
            time.sleep(.25)
        for i,case in enumerate(work['requests']):
            conn,response=request('/tokenize',{'content':case['prompt'],'add_special':True})
            data=response.read(1024*1024);conn.close()
            if response.status!=200:raise RuntimeError('Tokenization failed')
            ids=json.loads(data)['tokens']
            if not ids or len(ids)>2048:raise ValueError('Prompt token bound exceeded')
            body=dict(prompt=ids,n_predict=case['max_new_tokens'],temperature=0,seed=0,
                      stream=True,return_tokens=True,cache_prompt=False)
            emit(dict(event='request',index=i,body=body))
            start=time.monotonic_ns();conn,response=request('/completion',body,timeout=contract['limits']['timeout_s'])
            if response.status!=200:raise RuntimeError('Completion HTTP '+str(response.status))
            size=0;done=False
            while True:
                line=response.readline(1024*1024+1)
                if not line:break
                size+=len(line)
                if size>4*1024*1024 or len(line)>1024*1024:raise ValueError('SSE bound exceeded')
                if line.startswith(b'data: '):
                    raw=line[6:].decode().strip()
                    emit(dict(event='sse',index=i,elapsed_ns=time.monotonic_ns()-start,raw=raw))
                    if raw!='[DONE]' and json.loads(raw).get('stop') is True:done=True
            conn.close()
            if not done:raise RuntimeError('Incomplete completion stream')
            emit(dict(event='request_end',index=i,elapsed_ns=time.monotonic_ns()-start))
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        emit(dict(event='server_exit',returncode=process.returncode))


if __name__=='__main__':main()
