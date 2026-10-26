<!-- ai4r-human-report:1 -->
# Campaign observations

Execution and collection states describe infrastructure, not research correctness.

## Inputs and Setup

Campaign: case1-full-20261023-03

| Case | Repeat | App run | Execution | Collection |
| --- | ---: | --- | --- | --- |
| case1-cpu | 1 | run:f99f0f0756084186bff00fa2a57a73ec | halted | complete |

## Actual Output and Observations

### case1-cpu / repeat 1

Request: request-07931247e5c34bc28ebb3439e2976f8a

Task:

Using only the attached data, test whether logistic regression beats a 1-nearest-neighbour baseline by at least 5 points accuracy. Train on train.csv, write predictions for test.csv to predictions.csv, and report your conclusion and limitations.

Inputs and setup:

```json
{
  "inputs": [
    {
      "destination": "test.csv",
      "kind": "datasets",
      "path": "demos-20261023/case1-cpu/test.csv",
      "sha256": "83c211408fc478e6426d25057710d2e3e3e958410e250124c2ccb737c3b7d8a1",
      "size": 85806,
      "upload": true,
      "upload_record": {
        "content_sha256": "83c211408fc478e6426d25057710d2e3e3e958410e250124c2ccb737c3b7d8a1",
        "deleted_at": null,
        "filename": "test.csv",
        "id": "upload:24042565a9c8735725c788bb0386f1f8",
        "kind": "datasets",
        "resource_type": "validation_data",
        "schema_version": "1.0.0",
        "scope_id": "local",
        "size_bytes": 85806,
        "status": "uploaded",
        "stored_path": "workspace/input/datasets/local/test.csv",
        "text_sha256": null,
        "uploaded_at": "2026-10-23T14:38:24Z",
        "user_id": "account:6c5a319ddb5ca5725f547de5baa97e86"
      }
    },
    {
      "destination": "train.csv",
      "kind": "datasets",
      "path": "demos-20261023/case1-cpu/train.csv",
      "sha256": "8589c9819660549c7e088d53abf9a413394ab6bc054b49ea3c8fde04f7af9203",
      "size": 203146,
      "upload": true,
      "upload_record": {
        "content_sha256": "8589c9819660549c7e088d53abf9a413394ab6bc054b49ea3c8fde04f7af9203",
        "deleted_at": null,
        "filename": "train.csv",
        "id": "upload:e3bd1582903dbc5689c1638bcf1e00aa",
        "kind": "datasets",
        "resource_type": "validation_data",
        "schema_version": "1.0.0",
        "scope_id": "local",
        "size_bytes": 203146,
        "status": "uploaded",
        "stored_path": "workspace/input/datasets/local/train.csv",
        "text_sha256": null,
        "uploaded_at": "2026-10-23T14:38:24Z",
        "user_id": "account:6c5a319ddb5ca5725f547de5baa97e86"
      }
    },
    {
      "destination": "data-description.md",
      "kind": "docs",
      "path": "demos-20261023/case1-cpu/data-description.md",
      "sha256": "aac07dd9fd07008467fcf487b682017d5111444559022f1eb7bba71455a93c54",
      "size": 656,
      "upload": true,
      "upload_record": {
        "content_sha256": "aac07dd9fd07008467fcf487b682017d5111444559022f1eb7bba71455a93c54",
        "deleted_at": null,
        "filename": "data-description.md",
        "id": "upload:eea6d182041384396887f02e2c6e7683",
        "kind": "docs",
        "resource_type": "reference_document",
        "schema_version": "1.0.0",
        "scope_id": "local",
        "size_bytes": 656,
        "status": "uploaded",
        "stored_path": "workspace/input/docs/local/data-description.md",
        "text_sha256": "aac07dd9fd07008467fcf487b682017d5111444559022f1eb7bba71455a93c54",
        "uploaded_at": "2026-10-23T14:38:24Z",
        "user_id": "account:6c5a319ddb5ca5725f547de5baa97e86"
      }
    },
    {
      "destination": "provenance.py",
      "kind": "docs",
      "path": "case1-full-20261023-03/provenance.py",
      "sha256": "5badf267d60eaa52770904ced0dfad96c5a57a8e6c87fb3c4e96449e1bcc4b2f",
      "size": 823,
      "upload": false,
      "upload_record": null
    },
    {
      "destination": "runtime-meta.json",
      "kind": "docs",
      "path": "case1-full-20261023-03/runtime-meta.json",
      "sha256": "8b643dc540d88b7f42818055501aa2c625015c144bc7c9af5a35612cce5645d4",
      "size": 1036,
      "upload": false,
      "upload_record": null
    }
  ],
  "setup": [
    {
      "command": [
        "python",
        "inputs/provenance.py"
      ],
      "cwd": ".",
      "env": {},
      "id": "capture-runtime",
      "outputs": [
        "runtime-environment.json"
      ],
      "timeout_s": 20,
      "trusted": true
    }
  ],
  "limits": {
    "archive_member_limit": 100000,
    "cancel_grace_s": 30,
    "command_cpu_s": 30,
    "command_memory_mb": 512,
    "command_timeout_s": 30,
    "deadline_s": 7800,
    "max_artifact_bytes": 67108864,
    "max_files": 4096,
    "max_log_bytes": 1048576,
    "max_total_bytes": 134217728,
    "poll_s": 2
  }
}
```

Execution: halted; collection: complete.

[Saved run record](runs/case1-cpu-r1/run_record.json)

- [Artifact](runs/case1-cpu-r1/workspace/runtime-environment.json) — SHA-256: 2eaf9a01499f63d1567bd88de3e4e262476598c1350fd5d01918c79073a9b94e; bytes: 1398
- [Artifact](runs/case1-cpu-r1/artifacts/originals.zip) — SHA-256: dd92963d514093565a6f7fb8ba0e2ae90cdb7df6b0b7c80d725faa269de0c65a; bytes: 17255401
- [Artifact](runs/case1-cpu-r1/artifacts/originals.inventory.json) — SHA-256: 74241070febc7efedf5be9959e9314bec5200cca8618f222c532553698703798; bytes: 15926003
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-fe1d399fa9de67c959864920e43365bfed51d80f9ef77f242ba74d609f421825.txt) — SHA-256: 7a50a307f42846ed5ff6dc27f926a72809683ec761aebeb41035e6aa58ae4aac; bytes: 19425
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-125d3924f572db81cdd68bc6c553d06f1d3614a66aa8b2f42fed945396b0e4fa.txt) — SHA-256: fddb8b331e7829304f489d237f9b1f4f325cb55b5a306d24b20f0c9e1d4def02; bytes: 18718
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-3448f9ad959a37a5e197e6ae3d0ee8f94fd4fd0810c850202231c710cf29c7fa.txt) — SHA-256: 663e322208b447d8426ece2d0066bafbd5cf5640563432b4562f1beb356e8ce3; bytes: 36509
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-2aa113c1d563e9c51b1bb49c9463be3e234a5bd51bdb8b60702020e97e8052f9.txt) — SHA-256: b5c24cf05395572250fda1a9c1986cf4a8b3057127fa3dc32f4b36d1f430ee3d; bytes: 1742
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-1813b5aa75f42496265454d0a48a2ccc085f3f61a66f7d7736fc818665c8422d.txt) — SHA-256: b5c24cf05395572250fda1a9c1986cf4a8b3057127fa3dc32f4b36d1f430ee3d; bytes: 1742
- [Artifact](runs/case1-cpu-r1/artifacts/readable/verifi-93f42b4f860e19fc3473078c453dd044784c85dc041f439c7334cbbe0711351d.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case1-cpu-r1/artifacts/readable/intent-bb33a92b23e6b8f7bf1a487e1f6a75b1797c177ad9918259673bd4d2bfd521bc.txt) — SHA-256: 4188e32b215676e557541b5c333deec82f1dfdd2ad028720eacf0f522112f295; bytes: 3261
- [Artifact](runs/case1-cpu-r1/artifacts/readable/requir-f11583d12b7947956558dc715df7fafaf7b1da7421489388b4fc2a0cd344ffd2.txt) — SHA-256: 84e87546a59222368949dd78e570b3a5a3157c452634c58e70970841d221a065; bytes: 4890

Available observations:

```json
{
  "event_bytes": 7261,
  "event_cursor": 9,
  "event_files": [
    {
      "path": "events/0-e55a57fcd5bc43fb956f8a65339228be421670bc2a0e11ee52868fdee8445fb9.json",
      "sha256": "e55a57fcd5bc43fb956f8a65339228be421670bc2a0e11ee52868fdee8445fb9",
      "size": 1047
    },
    {
      "path": "events/2-6534df2558c5668402ef49b539e0c0c4c469deee13acb9f3d1953bf4f3b1ca03.json",
      "sha256": "6534df2558c5668402ef49b539e0c0c4c469deee13acb9f3d1953bf4f3b1ca03",
      "size": 3829
    },
    {
      "path": "events/5-c71ebea49c6664fd71f54496abef45e48b78d97fd9029ea3d74856c61ebf419b.json",
      "sha256": "c71ebea49c6664fd71f54496abef45e48b78d97fd9029ea3d74856c61ebf419b",
      "size": 1619
    },
    {
      "path": "events/8-8d29b5bf2dd6b2ad2cbc71165dd8d4770628ce88e1d32776b60564674b639952.json",
      "sha256": "8d29b5bf2dd6b2ad2cbc71165dd8d4770628ce88e1d32776b60564674b639952",
      "size": 766
    }
  ],
  "metrics": {
    "cpu": null,
    "disk": null,
    "gpu": null,
    "memory": null,
    "model_usage": null
  },
  "missing_metrics": [
    "CPU",
    "memory",
    "GPU",
    "model_usage"
  ],
  "sampling_scope": "app-exposed run events; no host attribution or zero inference"
}
```

Errors:

```json
[]
```

#### Assessment

<!-- review:case1-cpu-r1:assessment -->

<!-- /review -->

#### Evidence references

<!-- review:case1-cpu-r1:evidence_references -->

<!-- /review -->

#### Review notes

<!-- review:case1-cpu-r1:review_notes -->

<!-- /review -->

