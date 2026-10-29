# d_002465f0c181fe91e74ee091

This classification dataset contains four anonymous numeric features, two string
classes, 256 labeled training rows, and 512 test rows whose labels are withheld.

The public JSON uses schema `ai4r-classification-data:1` and contains exactly
`schema`, `dataset_id`, `feature_names`, `classes`, `train`, and `test`.
Training rows contain `id`, `features`, and `label`. Test rows contain only
`id` and `features`. Feature arrays follow `feature_names` order.

Choose and justify one bounded classifier intervention using the available
training evidence. Compare it with the unchanged captured baseline and report
the actual result, including a negative or inconclusive result.

The generic interface is `predict(train, test)`. Its input rows use the public
format above; it returns one string label from `classes` for each test row,
in the original test-row order. Trusted host scoring owns the held-out labels
and accuracy computation.
