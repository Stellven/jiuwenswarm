"""A declared separately admitted helper can use the same target-independent engine."""


def validate_adapter(profile):
    if not profile.get('required_test_refs') or not profile.get('parent_ref'):raise ValueError('independently admitted helper/test pins required')
    return profile
