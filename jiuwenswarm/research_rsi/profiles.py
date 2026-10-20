"""Frozen source ceilings and declaration-bound target profiles."""
from dataclasses import dataclass,asdict
from pathlib import PurePosixPath
import fnmatch
import math


class ProfileError(ValueError):pass


@dataclass(frozen=True)
class Limits:
    max_attempts:int=20
    max_no_progress:int=5
    wall_s:int=3600
    per_call_s:int=300
    session_query_limit:int=30
    lifetime_query_limit:int=90

    @classmethod
    def from_mapping(cls, values):
        ceilings=asdict(cls())
        if set(values)-set(ceilings):raise ProfileError('unknown limit')
        result=cls(**values)
        for key,value in asdict(result).items():
            if isinstance(value,bool) or not isinstance(value,int) or not 0<value<=ceilings[key]:raise ProfileError('limit exceeds source ceiling')
        if result.per_call_s>result.wall_s or result.session_query_limit>result.lifetime_query_limit:raise ProfileError('inconsistent limits')
        return result


def safe_path(value):
    p=PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value:raise ProfileError('unsafe mutable path')
    return value


def freeze_profile(profile,declaration,validate):
    validate('rsi-target-profile',profile)
    evolution=declaration.get('evolution',{})
    if evolution.get('rsi')!='propose':raise ProfileError('parent does not permit RSI proposals')
    permitted=[p[6:] for p in evolution.get('may_change',[]) if p.startswith('files:')]
    paths=[safe_path(x) for x in profile['mutable_paths']]
    if len(paths)!=1 or len(set(paths))!=len(paths):raise ProfileError('one mutable body required')
    for path in paths:
        if not any(fnmatch.fnmatchcase(path,p) for p in permitted):raise ProfileError('mutable path outside declaration')
    body={row['path']:row['sha256'] for row in declaration['identity']['body']}
    if paths[0] not in body or body[paths[0]]!=profile['parent_ref']['sha256']:raise ProfileError('target is not the exact declared parent body')
    if any(ref['sha256']==profile['parent_ref']['sha256'] for ref in profile['protected_refs']):raise ProfileError('protected reference overlaps mutable body')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0 for x in profile['limits'].values()):raise ProfileError('child limits must be positive')
    protected=profile.get('protected_paths',[])
    if any(fnmatch.fnmatchcase(path,p) for path in paths for p in protected):raise ProfileError('protected path overlap')
    splits=profile['splits']
    ids=[str(splits[k]) for k in ('development','hidden_loop','hidden_final','platform')]
    if len(set(ids))!=4:raise ProfileError('partitions must have distinct identities')
    if not 0<profile['session_query_limit']<=30 or not profile['session_query_limit']<=profile['lifetime_query_limit']<=90:raise ProfileError('query caps widened')
    return profile
