"""Explicit hardware identities shared by requests, labels and admission."""
PROFILES = {
    'jetson-orin': {'architecture': 'arm64', 'cuda': '12.6', 'sm': '87'},
    'spark-gb10': {'architecture': 'arm64', 'cuda': '13', 'sm': '121'},
}

def profile(target):
    name = target.get('profile') if isinstance(target, dict) else target
    if name not in PROFILES:
        raise ValueError('Unsupported target profile: ' + str(name))
    if isinstance(target, dict):
        for key, value in PROFILES[name].items():
            if key in target and target[key] != value:
                raise ValueError('Target ' + key + ' mismatch')
    return name

def labels(name):
    return {'campaign.target.profile': name, **{
        'factory.target.' + key: value for key, value in PROFILES[profile(name)].items()}}

def validate_image(target, row, build_target=None):
    name = profile(target)
    image_labels = row.get('Config', {}).get('Labels') or {}
    if row.get('Architecture') != PROFILES[name]['architecture'] or image_labels.get('campaign.target.profile') != name:
        raise ValueError('Image architecture or target profile mismatch')
    if build_target is not None and profile(build_target) != name:
        raise ValueError('Build target differs from task')
    # Historical Jetson receipts carry only campaign.target.profile.
    if name == 'spark-gb10' and any(image_labels.get(k) != v for k, v in labels(name).items()):
        raise ValueError('Spark image requires CUDA 13 and SM121 labels')
    return name


def admission_image_matches(admission, row):
    try:
        validate_image(admission.get('target_profile', 'jetson-orin'), row)
        return True
    except ValueError:
        return False
