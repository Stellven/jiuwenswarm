<!-- ai4r-human-report:1 -->
# Campaign observations

Execution and collection states describe infrastructure, not research correctness.

## Inputs and Setup

Campaign: requirements-v3-20261023-01

| Case | Repeat | App run | Execution | Collection |
| --- | ---: | --- | --- | --- |
| case1-cpu | 1 | run:6cfba611e7ef4f42b3fa3451a8573245 | halted | complete |

## Actual Output and Observations

### case1-cpu / repeat 1

Request: request-2beee70ae4ac46c6ac0859090163bb9a

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
      "path": "requirements-v3-20261023/provenance.py",
      "sha256": "5badf267d60eaa52770904ced0dfad96c5a57a8e6c87fb3c4e96449e1bcc4b2f",
      "size": 823,
      "upload": false,
      "upload_record": null
    },
    {
      "destination": "runtime-meta.json",
      "kind": "docs",
      "path": "requirements-v3-20261023/runtime-meta.json",
      "sha256": "538a563f21fc766fc67409477be36baf1a5e74e69a81db638ba8643c648df367",
      "size": 851,
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
    "deadline_s": 600,
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

- [Artifact](runs/case1-cpu-r1/workspace/runtime-environment.json) — SHA-256: eaca54b849ad835b499e968ad312c38470b3c67397f51f0e9ab92ecdf409f71b; bytes: 1213
- [Artifact](runs/case1-cpu-r1/artifacts/originals.zip) — SHA-256: 1663128ab298092ed9bdc986c6c2660acacbfd98c19548a2b8772d4e76f87bd3; bytes: 14488144
- [Artifact](runs/case1-cpu-r1/artifacts/originals.inventory.json) — SHA-256: 6a83edc0c71985c5b958888cac302c8225deba1652cce8a6fa7eb401c32eb324; bytes: 13250922
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-c36ab755264f619c26aaed817247dd7450fac463ed610270294fcf255c7adf35.txt) — SHA-256: 3406e108043e0dd0cad6b0130eedd46988984c96047438fba1d59b75275ef6ab; bytes: 18533
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-86b31d50c71329a36811c2dc524a84f49012fe7dd9d5f34baa8f385c3b8f72a6.txt) — SHA-256: a4792e1a905e033791f3660ed4f6c22118471f08d77528200bb02607e6a41cd6; bytes: 18718
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-6d6f7596dcea48da0804aa247736a52e473264d8c25fc18a7881eda84a7443af.txt) — SHA-256: 0c8c92ad9ef43fe25e2ca5cc2d488eb4bf86909875bb5d889722947eec48cb01; bytes: 29828
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-c974929abe9914995b8861fd974f58e3a5405a1e4891e0bbf874884e0eabe7f6.txt) — SHA-256: 4bc489ce002b034168925b3c3dd2fb312c6a8bd98bf28328200a218044853b24; bytes: 35639
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-ab9372e04904f8d3f45947cc037069c3fe4a226ca7da80a9e6c0824d8954444f.txt) — SHA-256: 94092172968c29186ca8b34c2557aea84ad8391d3e613879328ef65b63ace5d3; bytes: 456006
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-d9d67737a98058f75735b508ac67109c249162be706c56a1df60d824e32e3b01.txt) — SHA-256: 20ac27148beb16e3950ccce670598e16734ef41f8aeb7442db57ee7a4ee1480c; bytes: 1650
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-7c6f8c37162d9608a6a6aedbd7242aa3a911a18e41983e9902a471208781eecf.txt) — SHA-256: 20ac27148beb16e3950ccce670598e16734ef41f8aeb7442db57ee7a4ee1480c; bytes: 1650
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-47e558a990d1a1b10184927d5898be5d3c474b30c81fbff3b2300fd0d5fb592e.txt) — SHA-256: 1edafeab115a5b2091ad70cfc740920ec3ef2357f0a7c6bd5302bebc637dcffb; bytes: 1573
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-ed68d0dfc907f54819fd3392e3dcf73910e76dd4e011bd72ed3612ea6cef3923.txt) — SHA-256: 1edafeab115a5b2091ad70cfc740920ec3ef2357f0a7c6bd5302bebc637dcffb; bytes: 1573
- [Artifact](runs/case1-cpu-r1/artifacts/readable/verifi-31a05c2b2a76b8d094c4dced5b33a0641fa63b863b6cd0f4131c205e753ffa6e.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case1-cpu-r1/artifacts/readable/intent-5296f4a82d302b6dc7da9fc5c309e3aed551c94331ba21134881cccc3b4c086e.txt) — SHA-256: 4188e32b215676e557541b5c333deec82f1dfdd2ad028720eacf0f522112f295; bytes: 3261
- [Artifact](runs/case1-cpu-r1/artifacts/readable/verifi-b29392864ee31c13c38391c6e88c43a88ba73ecdd207ada640a1f86a064890c3.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case1-cpu-r1/artifacts/readable/requir-cbf4d6f9941533d359dfca5b2dc2d89ee9527339c4c9c25374b109f9df70348b.txt) — SHA-256: 84e87546a59222368949dd78e570b3a5a3157c452634c58e70970841d221a065; bytes: 4890
- [Artifact](runs/case1-cpu-r1/artifacts/readable/planne-8b96400185da459f09cdd2f1bca84b1cca17cac46f342d6e5503915809426c9d.txt) — SHA-256: ce1125e34d6c51808effbee196ae63d3c66af6badb293f994e43361f8a8c7b6c; bytes: 6443

Available observations:

```json
{
  "event_bytes": 9200,
  "event_cursor": 12,
  "event_files": [
    {
      "path": "events/0-071d4e1fefdf3138f0e49f13e8b159a1785529b7aa6d334921ffb7457f7d2d9f.json",
      "sha256": "071d4e1fefdf3138f0e49f13e8b159a1785529b7aa6d334921ffb7457f7d2d9f",
      "size": 1047
    },
    {
      "path": "events/2-dde2d4e551aa89d2f5aa6cc1282b5bd78439ef89f6ae7d654702642d7f3c8a25.json",
      "sha256": "dde2d4e551aa89d2f5aa6cc1282b5bd78439ef89f6ae7d654702642d7f3c8a25",
      "size": 3762
    },
    {
      "path": "events/5-60584d5cd44b4070843fa091028b6b9ef45b52e2f98a2079575db45b03b24550.json",
      "sha256": "60584d5cd44b4070843fa091028b6b9ef45b52e2f98a2079575db45b03b24550",
      "size": 1198
    },
    {
      "path": "events/7-481bc052c961a403fee06c2a28613d643fab392139b58c43602789f1599ae369.json",
      "sha256": "481bc052c961a403fee06c2a28613d643fab392139b58c43602789f1599ae369",
      "size": 1637
    },
    {
      "path": "events/10-222ff57aaa9db8ea37aa56371d368b925ee396f15703e82f887647953acc9eab.json",
      "sha256": "222ff57aaa9db8ea37aa56371d368b925ee396f15703e82f887647953acc9eab",
      "size": 778
    },
    {
      "path": "events/11-d6eeab3b5917fd62d3a518dd6d616adcf5fb9874d675ff2296d33f9e44b4fda6.json",
      "sha256": "d6eeab3b5917fd62d3a518dd6d616adcf5fb9874d675ff2296d33f9e44b4fda6",
      "size": 778
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
[
  {
    "at": "2026-10-23T16:07:56Z",
    "category": "app_access_failure",
    "detail": "product HTTP refused operation: 409"
  }
]
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

