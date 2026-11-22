# Factory runs helpers

The Factory runs web API (`jiuwenswarm/gateway/channel_manager/web/factory_http.py`) imports these helpers:

- `prepare_inspection_home.py` prepares an isolated factory home for a read-only capsule inspection session. It uses `prepare_star_home.py` to copy the operator's Codex sign-in into that home.
- `recorder_live_demo.py` runs the recorder evidence walkthrough (`recorder-evidence-walkthrough.json`) as a live factory session against retained evidence. It loads no model.
- `build_demo_replays.py` builds the curated replay bundles (`factory.curated-replay/1`) that the Factory runs page shows as one test from contract to result:

  ```bash
  python -m scripts.spark.build_demo_replays --base <run workspace> --out <exports dir> --replace
  ```

Run them from the repository root with the checkout's Python. See the [API contract](../../docs/architecture/factory/FACTORY-RUNS-HTTP.md).
