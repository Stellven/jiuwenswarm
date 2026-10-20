"""Launch only the protected router selection service."""
import argparse
import asyncio
import os
from pathlib import Path
import stat

from .catalog import reject_credentials
from .contracts import ContractData
from .engine import DecisionEngine
from .request_validation import ProtectedData, strict_json
from .service import RouterService


def load_config(path):
    p=Path(path)
    if not p.is_absolute() or any(v.is_symlink() for v in (p,*p.parents)):raise ValueError('Unsafe router configuration path')
    fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1 or meta.st_mode&0o022 or meta.st_size>65536:raise ValueError('Unsafe router configuration custody')
        with os.fdopen(fd,'rb',closefd=False) as stream:config=strict_json(stream.read(65537))
    finally:os.close(fd)
    required={'socket_path','audit_root','allowed_peer_uids','data_roots','catalog_ref','profile_refs','development_profiles_ref','adapter_revision'}
    optional={'ref_index_path','ref_index','contract_data_root'}
    if not isinstance(config,dict) or not required<=set(config) or set(config)-required-optional:raise ValueError('Unknown router configuration field')
    reject_credentials(config)
    if config['allowed_peer_uids']!=[10001] or not config['data_roots'] or not isinstance(config['profile_refs'],list) or not isinstance(config['adapter_revision'],str) or not config['adapter_revision']:raise ValueError('Invalid router role/pins')
    for value in [config['socket_path'],config['audit_root'],*config['data_roots']]:
        root=Path(value)
        if not root.is_absolute() or any(p.is_symlink() for p in (root,*root.parents)):raise ValueError('Unsafe router resource path')
        if any(root==Path(p) or root.is_relative_to(Path(p)) for p in ('/var/lib/ai4r','/var/lib/ai4r-accounts','/hidden-fixtures','/var/lib/ai4r-rsi')):raise ValueError('Router cannot receive private product/custody roots')
    if config.get('ref_index_path') is not None:
        index=Path(config['ref_index_path'])
        if not index.is_absolute() or not any(index.is_relative_to(Path(root)) for root in config['data_roots']):raise ValueError('Router index is outside the public data roots')
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["serve"])
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    if not hasattr(os,'geteuid') or os.geteuid()!=10011:raise ValueError('Router requires its separate credential-free UID')
    config = load_config(args.config)
    allowed_env = {k:v for k,v in os.environ.items() if k in {"PATH", "LANG", "LC_ALL", "TZ", "PYTHONUTF8"}}
    os.environ.clear(); os.environ.update(allowed_env)
    data = ProtectedData(config["data_roots"], ref_index=config.get("ref_index", {}),ref_index_path=config.get('ref_index_path'))
    engine = DecisionEngine(data=data, validate=ContractData(config.get("contract_data_root")).validate,
        audit_root=config["audit_root"], catalog_ref=config["catalog_ref"], profile_refs=config["profile_refs"],
        development_profiles_ref=config["development_profiles_ref"], adapter_revision=config["adapter_revision"])
    service = RouterService(engine, config["allowed_peer_uids"])
    try: asyncio.run(service.serve(config["socket_path"]))
    except KeyboardInterrupt: pass
    finally: engine.store.close()


if __name__ == "__main__": main()

