# Source map

- Legacy C4 `e26cda7b058ce0c8f9df5076b14f535cc78e2da9` checks the actual native
  bank pointer in `src/llama-context.cpp:5229`. `src/llama-expert-predict.cpp:491`
  refuses operation with the native cache after the single-slot check.
- Legacy `src/llama-expert-predict.cpp:266` issues `MADV_WILLNEED`, while lines
  386–438 compare predictions with selected experts and record submitted
  advice lead. The shutdown line fixes useful bytes at zero. These observations
  establish no predictive slot upload on the stock native bank.
- Legacy predictor source SHA-256 is
  `291beff149a43ab7b3f7992a0be4af3b9b8f1c95e01f8ead5acf224a133109a3`.
  The legacy context SHA-256 is
  `29a46963ef520771719ccbcf4bc74b36f3dfade3e1c75b018ff8c1628ae06a08`.
- `routing.build_expert_demand_predictor` 1.2.0 defines observed lifecycle
  counters for the new native-bank mechanism. The analysis consumes raw
  terminal marker records and authentic stock/candidate cap receipts. A future
  source revision that changes the marker contract needs a matching analyzer
  version. SHA256SUMS pins the analysis itself.
