"""Reviewer-side arithmetic only. Never upload this script or hidden labels.

Usage: python score_predictions.py path/to/predictions.csv [baseline_predictions.csv]
This records measurements, not an automatic quality verdict.
"""
import csv
import json
from pathlib import Path
import sys


def read_rows(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ['id', 'label']:
            raise ValueError('Expected exactly id,label columns')
        result = {}
        for row in reader:
            if not row['id'] or row['id'] in result or row['label'] not in {'0', '1'}:
                raise ValueError('Invalid label, empty ID or duplicate ID')
            result[row['id']] = row['label']
        return result


def measure(path, truth):
    prediction = read_rows(path)
    if set(prediction) != set(truth):
        raise ValueError('Predictions must cover the exact blind test IDs once each')
    correct = sum(prediction[key] == label for key, label in truth.items())
    return {'file': str(path), 'correct': correct, 'sample_count': len(truth),
            'accuracy': correct / len(truth)}


if __name__ == '__main__':
    if len(sys.argv) not in {2, 3}:
        raise SystemExit(__doc__)
    truth = read_rows(Path(__file__).parent / 'test_labels.csv')
    result = {'measurement': measure(sys.argv[1], truth), 'quality_assessment': None,
              'scope': 'Independent reviewer-only count; this is not the app verifier or an automatic judge.'}
    if len(sys.argv) == 3:
        result['baseline'] = measure(sys.argv[2], truth)
        result['accuracy_gap_points'] = 100 * (result['measurement']['accuracy'] - result['baseline']['accuracy'])
    print(json.dumps(result, indent=2))
