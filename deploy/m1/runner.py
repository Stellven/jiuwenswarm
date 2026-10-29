"""Compatibility entry point for the integrated repository operator."""
import os
import sys
from ai4r import main

if __name__ == '__main__':
    profile = os.environ.get('AI4R_OPERATOR_PROFILE')
    raise SystemExit(main((['--profile', profile] if profile else []) + ['runner', *sys.argv[1:]]))
