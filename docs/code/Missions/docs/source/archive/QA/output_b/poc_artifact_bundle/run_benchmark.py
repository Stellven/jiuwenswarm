"""Measure exactly one treatment observation on the frozen held-out split.

Protected Benchmark, not this treatment harness, controls baseline-first
ordering and repeat aggregation: it completes the three baseline jobs before
invoking this script once for each of three treatment jobs. This script neither
imports nor executes the baseline and does not aggregate or classify outcomes.

No execution or measurement was performed during this Builder call. Resource
custody and actual execution order remain protected host checks. This tiny
authored demonstration and repeated fixed split cannot establish generalization
across independent datasets or splits.
"""

import json
import random
from pathlib import Path

import poc_patch


SEED = 42
VALIDATION_PATH = Path('/resources/validation/data.json')


def main():
    random.seed(SEED)
    data = json.loads(VALIDATION_PATH.read_text(encoding='utf-8'))
    predict = poc_patch.fit_classifier(data['train'])
    accuracy = sum(row['label'] == predict(row['x']) for row in data['test']) / len(data['test'])
    print(json.dumps({"metrics": {"accuracy": accuracy}}, allow_nan=False))


if __name__ == '__main__':
    main()
