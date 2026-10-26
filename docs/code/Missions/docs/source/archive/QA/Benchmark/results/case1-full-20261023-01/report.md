<!-- ai4r-human-report:1 -->
# Campaign observations

Execution and collection states describe infrastructure, not research correctness.

## Inputs and Setup

Campaign: case1-full-20261023-01

| Case | Repeat | App run | Execution | Collection |
| --- | ---: | --- | --- | --- |
| case1-cpu | 1 | run:ed6087d37f4742aaba2b0435a1f91841 | partial | complete |

## Actual Output and Observations

### case1-cpu / repeat 1

Request: request-8ffc1f13bc2d4153818c47d9aa4a7361

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
      "path": "case1-full-20261023-01/provenance.py",
      "sha256": "5badf267d60eaa52770904ced0dfad96c5a57a8e6c87fb3c4e96449e1bcc4b2f",
      "size": 823,
      "upload": false,
      "upload_record": null
    },
    {
      "destination": "runtime-meta.json",
      "kind": "docs",
      "path": "case1-full-20261023-01/runtime-meta.json",
      "sha256": "690fe4c483b241812ef01e6338007b5acc3fcedf0b6b94afa273bbfbefdb3af3",
      "size": 912,
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

Execution: partial; collection: complete.

[Saved run record](runs/case1-cpu-r1/run_record.json)

- [Artifact](runs/case1-cpu-r1/workspace/runtime-environment.json) — SHA-256: 9129ffd81f737112e598737edb0aab15116d0bb9a08b72b5c55a46ea67eff702; bytes: 1274
- [Artifact](runs/case1-cpu-r1/artifacts/originals.zip) — SHA-256: 2c2aed0f1482f6c26c8a2f2e730ed01bb22588258256decf58c951c396ffca32; bytes: 38741896
- [Artifact](runs/case1-cpu-r1/artifacts/originals.inventory.json) — SHA-256: 879fc1fb82993371cd897c3d2afcf8f03de8f93bd9fee30e1660f0eca5a19bd4; bytes: 35122293
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-67332f4cd1d00bbec0fc2b26a60869aa6fde4efbe554032be78c45f9727fd026.txt) — SHA-256: af073619d9a6a2026bdf612829fca148f8e55b398c7ece742fa236f294a05a53; bytes: 107100
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-cc88f16b7af42f8a6bd8a29976b8ddbd03cebce7924c52bd2f4af956bb3e8a50.txt) — SHA-256: a74295d8e260114fcc28c8dbd883e39f3723eedcfce4bf7697de49d33e83f799; bytes: 25832
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-6deb6b2a0034208feb8c3ee8105c5b94a631aeb92ba184dc7cde5dfeaccc4595.txt) — SHA-256: dbeadfd1c7a2d23643466f97960cf7915f8112fb17214c69a5d758a70115630e; bytes: 135372
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-dbd062c22f2b38b3b9df1cae0ab95adb97ce259259bca47f9ab2191791e44f6d.txt) — SHA-256: 4f6222890028b251a11eff955419e8cb7a825a4de0ced93f320c216b98fcbb3f; bytes: 18559
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-9c5c8ff94e39c60500a7e8e1d988182ea6547eacee00282c26ba609101b2bead.txt) — SHA-256: 5aa1784767e17d67586cf6466648c697f2e774013e371860e111b402b546051d; bytes: 18718
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-84d81ddcb238d5d7849a73857f88395b823b5dac990b98d28118e675871e765a.txt) — SHA-256: 32dea8d277c024ee7a664752dcb7fe880f10895891a2dba9ac195a495edf88a6; bytes: 30351
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-ad7fd6cb977884059c5855ecf6b950dd0a56c968e226e1e0fcde8f4199465718.txt) — SHA-256: 7fc2b5fb93fb59159c1ea8dc4f0ac96d55006023234f8ee2fe07e6968e553a20; bytes: 35663
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-c8d7b89f133d14d6f2797a600eca3ee1bdc5a8403849935a39256f58567220e0.txt) — SHA-256: 1ebfc1e76a320363b8f8c0361e8d7d434fa75229e60ba93168d952ec39b2c781; bytes: 37149
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-1f1ad20bed5d88b7eb398ecb1e70c15e0271bdac16bccdbb8769ae967febc1eb.txt) — SHA-256: e6991c8e0d3b238822703295f31bc5a49426696afe33c9b4e85f92542357d590; bytes: 456562
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-94f3c6aef8ba61db10ac1e1d3dd39d4324899831454bc3d9c5a4e4cf2a6fe20d.txt) — SHA-256: 9fbb307b72724a7a806c35a7ea1fc00c85b874f1cc4ac938d67017791b810391; bytes: 24231
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-979f866aa18bf8b08481548a47103d1cd20b40b5033dbe7cffd4dd222f7b8d7c.txt) — SHA-256: df8a6def94fb5f37196fcb68ca03ea8e4454762b6a50099059df85f99991afba; bytes: 23204
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-020a0b6dfa31516d44dcf1d622a50be9be594e306a8a33a5c16a2713b50ad586.txt) — SHA-256: d2dcac020112fcc90b369da490e78f5726ab04584d722a70da1eed5603b592de; bytes: 25570
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-a959f9c84b81aceea1a5da87dc26857dba5db34f203064cd309b0b4b0fd07668.txt) — SHA-256: c39dcf08e02eac80910a883f17db841cc41ce0a8dffdc77ca7348fe757f7dbad; bytes: 21112
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-dc278c153a8105d69462f33154bf93eaf438be1645173ef2d057f62f5033b409.txt) — SHA-256: 3c8f0b45ccb5c1ccca0244a5b3358a5b467b07bec348c0120a0ae50852b039a0; bytes: 19220
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-c7454b95eb9a2a609737d462cb7027efcdb89b451a90488644d64c02744dc18b.txt) — SHA-256: aaee5cf63756dba4a4c6034c6e8fd9e5a2233f097877c07e3c7d4626ff6cb584; bytes: 17130
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-3ab585ccaaeaaba7b221898ea2fbdb6b25097b35ad69b871c220975ec079d44e.txt) — SHA-256: af110ee5b9cf4bf81329fa37a4d79ffbdff13a35431660548f4647e9c2d87ba9; bytes: 2715
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-0c11e06d45cff6c5823730f6461f00bb7d0ed308239bec7192457b19badd9b95.txt) — SHA-256: af110ee5b9cf4bf81329fa37a4d79ffbdff13a35431660548f4647e9c2d87ba9; bytes: 2715
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-ad95241b6e1c0f9a7649a7f4b0bc7e53aff5aa52447b63ca6afbf43b3d2c4245.txt) — SHA-256: 4198701a35cf7bea34c8e6464f52603aafc17bc05bcd7d0af946447986af66f2; bytes: 1752
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-31ccb0b3d938f80ae6add3cf928da79bafa1f5f43da46854505deae0f654ae79.txt) — SHA-256: 4198701a35cf7bea34c8e6464f52603aafc17bc05bcd7d0af946447986af66f2; bytes: 1752
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-162c1862610f51aafdb0ae9926dbeb73fa5d2430a8e34ef961afdc7011bf031d.txt) — SHA-256: b2a018694eecfdbd078b54bd22bbb73c41025cd352791362648f4bd645f4f3b6; bytes: 1541
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-a9146a024f7588bbeb934a9278547c0a9e35b8c70729d7a7742f4cf952493b82.txt) — SHA-256: b2a018694eecfdbd078b54bd22bbb73c41025cd352791362648f4bd645f4f3b6; bytes: 1541
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-74b7ac02f073ed144ad9c514d01beb968f0e6cc3e970b42769e96a6370763939.txt) — SHA-256: 6c026d28adf0e82c3fcc1ab529ef1753a2186b89fcc5711c9235f007e722d6d0; bytes: 2448
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-22f9764e19fdfccda98ce7598cee6323ca8018cf3bd8439e0bf3be716a7bebff.txt) — SHA-256: 6c026d28adf0e82c3fcc1ab529ef1753a2186b89fcc5711c9235f007e722d6d0; bytes: 2448
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-fe21e5a48bc6bc4e6f41523144678c1cf741bad218e7fa9652e30f2dd5cee189.txt) — SHA-256: 50ffeb45e5b35da2150d08f5116bf05edf175b28d9dedd707c49095edf5e486d; bytes: 1580
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-779bbbe0fa9bf7a08b877b06a212246e6f2f47ff28e335a3c2d79e318ab3ad36.txt) — SHA-256: 23142a3c00193e458be55fe51ed2fc5a8fa6d53713a29517c168ed738c149364; bytes: 2155
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-c62026d4f6b903d781ae2d0a489a38db150e1b4b8135507d69fcdc566e7632a6.txt) — SHA-256: 50ffeb45e5b35da2150d08f5116bf05edf175b28d9dedd707c49095edf5e486d; bytes: 1580
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-a7633e0f2814d47525bf96d19802ed6d8d8a73f9eed6f8a2fbc6d5342e652c9e.txt) — SHA-256: 23142a3c00193e458be55fe51ed2fc5a8fa6d53713a29517c168ed738c149364; bytes: 2155
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-8d7c83ab0f053871e84d244a46b89d5bcf37a72e296a09e87cccde27469b1a0e.txt) — SHA-256: bc86bc0e1d2913141b1b4c262c88c14fc952323b4749172011cddf62482f3892; bytes: 2517
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-f3badcb8621dcaf0b1f6bd68fe5aab0d47942ebf609866b738ffeccf0942aa64.txt) — SHA-256: bc86bc0e1d2913141b1b4c262c88c14fc952323b4749172011cddf62482f3892; bytes: 2517
- [Artifact](runs/case1-cpu-r1/artifacts/readable/rankin-5fd8c9fbbfb852f89b2411b9e6728564fac27c997391e4d12351405458647f3b.txt) — SHA-256: 844fd0c3bec0b70e53c350ed8474889f8a730a49fa7e917a10ba76a6ab504e7f; bytes: 1241
- [Artifact](runs/case1-cpu-r1/artifacts/readable/screen-db634ac5d5d019f8a3ba4676347c5fdf60f61d5d503249ebc780f5ae2f7121fc.txt) — SHA-256: 11336f6ccbf243bd1d7dc3b719bdb1ee77a7cc07472e61d36ccd78657aa586e2; bytes: 216
- [Artifact](runs/case1-cpu-r1/artifacts/readable/verifi-c97253641cd2879f871361b98ea6edb58b467d26901c7983a7eb8b47770f61d5.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956

Available observations:

```json
{
  "event_bytes": 26525,
  "event_cursor": 44,
  "event_files": [
    {
      "path": "events/0-3d5e0d2c86b22ec1f4ab4939987607ddeac3bcc1abe8bdee1943c47f98ba755d.json",
      "sha256": "3d5e0d2c86b22ec1f4ab4939987607ddeac3bcc1abe8bdee1943c47f98ba755d",
      "size": 1047
    },
    {
      "path": "events/2-ff5b246782326ad1167e3e03c82954e89fbf014c9480a7ec10a80819e98d0d12.json",
      "sha256": "ff5b246782326ad1167e3e03c82954e89fbf014c9480a7ec10a80819e98d0d12",
      "size": 3835
    },
    {
      "path": "events/5-dc04adf4631758ba16860487e81fa68f3c020501f92f1f0c26b973deb115f9d9.json",
      "sha256": "dc04adf4631758ba16860487e81fa68f3c020501f92f1f0c26b973deb115f9d9",
      "size": 1198
    },
    {
      "path": "events/7-65e19b89519a7eaac12dece9c3c193a6c4f253fbefd9a4fc6d4890d23a965d8d.json",
      "sha256": "65e19b89519a7eaac12dece9c3c193a6c4f253fbefd9a4fc6d4890d23a965d8d",
      "size": 1637
    },
    {
      "path": "events/10-3bb616bfeef2234b6abc817573c301fe88f216686eebe0a944fc61a62eb2981f.json",
      "sha256": "3bb616bfeef2234b6abc817573c301fe88f216686eebe0a944fc61a62eb2981f",
      "size": 778
    },
    {
      "path": "events/11-ea2597182a89c63c3e40d4ed5df6c66f1a2ce5a6b3ba07badd3adff8ba1c4ed4.json",
      "sha256": "ea2597182a89c63c3e40d4ed5df6c66f1a2ce5a6b3ba07badd3adff8ba1c4ed4",
      "size": 1189
    },
    {
      "path": "events/13-9a645d7a5d77423db6edcb5cadeb7f24e65ddfa68d884f693247f2d0a6f3618b.json",
      "sha256": "9a645d7a5d77423db6edcb5cadeb7f24e65ddfa68d884f693247f2d0a6f3618b",
      "size": 1611
    },
    {
      "path": "events/16-f09d4ecc2d039cf678af51fdc2e9da776e502c6bb7f4c30c4fc41f6d6ea981a4.json",
      "sha256": "f09d4ecc2d039cf678af51fdc2e9da776e502c6bb7f4c30c4fc41f6d6ea981a4",
      "size": 1173
    },
    {
      "path": "events/18-2ae0de668686950ec0934f8daceafaa92b0b80e25f9c3ce7e3e599c2fafa4a17.json",
      "sha256": "2ae0de668686950ec0934f8daceafaa92b0b80e25f9c3ce7e3e599c2fafa4a17",
      "size": 1580
    },
    {
      "path": "events/21-8d02e7fabbf6fcb79ec24fe5898096a9c9448796c9012119c3de203f65c96d8c.json",
      "sha256": "8d02e7fabbf6fcb79ec24fe5898096a9c9448796c9012119c3de203f65c96d8c",
      "size": 2000
    },
    {
      "path": "events/25-c4824186b61fe12bee2a34a5996063c315de74c96614c5f1c3dc4d0383e8c6f8.json",
      "sha256": "c4824186b61fe12bee2a34a5996063c315de74c96614c5f1c3dc4d0383e8c6f8",
      "size": 1175
    },
    {
      "path": "events/27-b942bbb3921d939e693c0d1608ecdd2ec1ab47890ae66e7e9a465f043bbc4024.json",
      "sha256": "b942bbb3921d939e693c0d1608ecdd2ec1ab47890ae66e7e9a465f043bbc4024",
      "size": 1618
    },
    {
      "path": "events/30-3f97c17189356bdbb5ae0d781ecc8a014a001b33848026df4c2c6469d5136def.json",
      "sha256": "3f97c17189356bdbb5ae0d781ecc8a014a001b33848026df4c2c6469d5136def",
      "size": 2062
    },
    {
      "path": "events/34-38b454804d045d40742b4dfdcf8d32f58697ce326ff3ac9b3c7dcd1af8fdba53.json",
      "sha256": "38b454804d045d40742b4dfdcf8d32f58697ce326ff3ac9b3c7dcd1af8fdba53",
      "size": 1201
    },
    {
      "path": "events/36-d8d46e5d1e16000f07113fdc9b5b8cd8738095c91278bef2d334352ea9feb89a.json",
      "sha256": "d8d46e5d1e16000f07113fdc9b5b8cd8738095c91278bef2d334352ea9feb89a",
      "size": 2072
    },
    {
      "path": "events/40-2d1fa544b966521dc0577c2161bb0e4cf2fc8a176a854bbea28f41cf00fb0857.json",
      "sha256": "2d1fa544b966521dc0577c2161bb0e4cf2fc8a176a854bbea28f41cf00fb0857",
      "size": 1597
    },
    {
      "path": "events/43-a6ee896e6adfacc0fcd4a3eef9c6cf1c1656834215d3e34c66e81c06aeaaace8.json",
      "sha256": "a6ee896e6adfacc0fcd4a3eef9c6cf1c1656834215d3e34c66e81c06aeaaace8",
      "size": 752
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

