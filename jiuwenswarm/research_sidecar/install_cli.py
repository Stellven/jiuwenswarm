"""Build-time installation of the three fixed public command names."""
from pathlib import Path


def install(root='/usr/local/bin'):
    for command,function in [('benchmark-runner','runner_main'),('benchmark-referee','referee_main'),('benchmark-report','report_main')]:
        path=Path(root)/command
        path.write_text('#!/usr/local/bin/python\nfrom jiuwenswarm.research_sidecar.cli import '+function+'\nraise SystemExit('+function+'())\n',encoding='utf8')
        path.chmod(0o755)


if __name__=='__main__':install()
