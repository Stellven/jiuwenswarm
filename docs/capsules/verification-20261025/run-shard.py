from pathlib import Path
import subprocess,sys
n=int(sys.argv[1]); assert 0<=n<4
root=Path('/mnt/c/Users/m50066326/huawei/AI4Research-Development/jiuwenswarm-m1-reviewed-integration')
files=sorted(str(p.relative_to(root)) for p in (root/'tests/unit_tests/research').glob('test_*.py'))
args=[sys.executable,'-m','pytest','-o','addopts=','-o','log_cli=false','-q','-p','ai4r_live_failures',
      '--timeout=60','--tb=short','--maxfail=12','--basetemp',f'/var/tmp/ai4r-merged-unit-{n}',
      f'--junitxml=/tmp/ai4r-merged-unit-{n}.xml',*files[n::4]]
with open(f'/tmp/ai4r-merged-unit-{n}.log','w') as out:
    print('Command:',repr(args),file=out,flush=True)
    result=subprocess.run(args,cwd=root,stdout=out,stderr=subprocess.STDOUT)
print('Shard',n,'exit',result.returncode,flush=True)
raise SystemExit(result.returncode)
