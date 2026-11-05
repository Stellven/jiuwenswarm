"""Build the service and bind its immutable local application image ID."""
from pathlib import Path
import re
import subprocess


def main():
    folder = Path(__file__).resolve().parent
    subprocess.run(['docker', 'build', '-t', 'cc-demo/compute:1', '.'], cwd=folder, check=True)
    image = subprocess.check_output(
        ['docker', 'image', 'inspect', '--format', '{{.Id}}', 'cc-demo/compute:1'],
        text=True).strip()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('Docker returned an invalid image ID')
    path = folder / 'cc.yaml'
    updated, count = re.subn(r'(?m)^(\s*image:)\s*\S+\s*$', lambda m: m[1] + ' ' + image,
                             path.read_text(encoding='utf-8'))
    if count != 1:
        raise ValueError('Expected exactly one image binding')
    updated = re.sub(r'(?m)^\s*# Base-image digest only until build_image.py can bind the built application ID.\n', '', updated)
    path.write_text(updated, encoding='utf-8')
    print(image)


if __name__ == '__main__':
    main()
