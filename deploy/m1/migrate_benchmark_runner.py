"""Retired workstation migration. Unknown live state must not be adopted."""
import argparse

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.error('Use ai4r.py setup with a new project/profile. Existing installations remain intact; automatic adoption is unavailable. Migrate existing volumes/configuration explicitly with their operator.')
