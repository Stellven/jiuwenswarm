"""Compatibility credential refresh using the repository-owned operator."""
import argparse
from ai4r import main

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile')
    p.add_argument('--refresh-credential', action='store_true', required=True)
    args = p.parse_args()
    raise SystemExit(main((['--profile', args.profile] if args.profile else []) + ['start', '--refresh-credential']))
