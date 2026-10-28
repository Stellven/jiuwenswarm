# Externally supplied classification project

Public data.json contains dataset_id, feature_names, classes, labelled train rows
and unlabelled test rows. Each row has an opaque id and a finite numeric features
array. Only train rows have label. Test labels and the generation seed are private
to an independent evaluator and are unavailable to model or generated code.
Choose and justify a classifier using the supplied training data. Keep the captured
majority-class baseline and public data unchanged. Implement predict(train, test)
in poc_patch.py, returning one declared string label per test row in test order.
run_benchmark.py reads /resources/validation/data.json and prints exactly one JSON
object: {"predictions": [{"id": "<test row id>", "label": "<declared class>"}]}.
It must cover every test id exactly once and must not emit metrics or accuracy.
The trusted host scores successful predictions after the sandbox has stopped.
Use only the Python standard library, no network, GPU or external data. Baseline
runs precede treatment runs, three repeats each, fixed execution seed 42. Accuracy
is the fraction of correct predictions. Improvement succeeds only if treatment
accuracy exceeds baseline accuracy; equality or lower falsifies the claim.
Preserve negative and inconclusive outcomes and report uncertainty and limitations.

Accuracy and the success threshold are to be reported in percent on a 0-100 scale.
