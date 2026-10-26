# Local CPU classification project

This built-in educational project has actual captured Python and JSON files.
The baseline always predicts the training majority class. Improve only the
classifier in poc_patch.py, for example by fitting the midpoint between class
means on the training split. Preserve the held-out test split, the accuracy
measurement, baseline, and registered success/falsification comparisons. The
classifier cutoff is the intervention and may change. Metric ID is accuracy (fraction,
higher is better). Use no dependencies, network, GPUs, or external data. Run the
frozen baseline first and then the treatment, at least three repeats each. A
successful result requires treatment accuracy > baseline accuracy; equality or
lower falsifies the improvement claim. Report genuine measured values and the
limitations of this tiny authored demonstration. Data is /resources/validation/data.json.
