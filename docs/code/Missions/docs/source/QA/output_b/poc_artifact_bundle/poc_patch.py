"""Purpose: fit a scalar midpoint classifier using training data only.

This standalone bounded patch reads no files and edits no files. The two
training class means determine the cutoff and the corresponding class sides.
"""


def fit_classifier(train):
    labels = sorted({row['label'] for row in train})
    if len(labels) != 2:
        raise ValueError('The frozen intervention requires exactly two classes.')
    means = {}
    for label in labels:
        values = [row['x'] for row in train if row['label'] == label]
        means[label] = sum(values) / len(values)
    low_label, high_label = sorted(labels, key=means.__getitem__)
    if means[low_label] == means[high_label]:
        raise ValueError('Distinct class means are required to assign sides.')
    cutoff = (means[low_label] + means[high_label]) / 2

    def predict(x):
        return low_label if x < cutoff else high_label

    return predict
