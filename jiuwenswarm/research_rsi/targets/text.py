"""Conditional text target needs a declared body and a frozen independent rubric."""


def validate_text_target(profile,*,native_headless_ready):
    if not native_headless_ready:raise RuntimeError('BLOCKED: bounded headless native transport unavailable')
    if not profile.get('required_test_refs') or any('referee' in p.lower() for p in profile['mutable_paths']):raise ValueError('protected text referee or missing required tests')
    return profile
