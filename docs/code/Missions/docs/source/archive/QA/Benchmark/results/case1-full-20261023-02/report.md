<!-- ai4r-human-report:1 -->
# Campaign observations

Execution and collection states describe infrastructure, not research correctness.

## Inputs and Setup

Campaign: case1-full-20261023-02

| Case | Repeat | App run | Execution | Collection |
| --- | ---: | --- | --- | --- |
| case1-cpu | 1 | run:1ca32733f3e04c188616d16ecf315ac7 | partial | complete |

## Actual Output and Observations

### case1-cpu / repeat 1

Request: request-d0e340f7851f493bb3a2b50607d2a898

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
      "path": "case1-full-20261023-02/provenance.py",
      "sha256": "5badf267d60eaa52770904ced0dfad96c5a57a8e6c87fb3c4e96449e1bcc4b2f",
      "size": 823,
      "upload": false,
      "upload_record": null
    },
    {
      "destination": "runtime-meta.json",
      "kind": "docs",
      "path": "case1-full-20261023-02/runtime-meta.json",
      "sha256": "a969b30861f43b75fd278426ea26a7cbcf6a39a32a089b6efc3bae2a13d217ef",
      "size": 968,
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

- [Artifact](runs/case1-cpu-r1/workspace/runtime-environment.json) — SHA-256: b0f30a5f86faed51bac4890840e49980f3aeed2ebd90bb743927eae6474440d8; bytes: 1330
- [Artifact](runs/case1-cpu-r1/artifacts/originals.zip) — SHA-256: 9d917a5baf306dc1c808380295639b83d74f54bdc94f7b62dcedc84258d1d773; bytes: 29539783
- [Artifact](runs/case1-cpu-r1/artifacts/originals.inventory.json) — SHA-256: 4cacdc857f3ae62cdec2dc69f8a498e2ca7a0dcc51d36e0889cd4f547d56c229; bytes: 26856468
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-0bfcb94d309475197b39f1e85cf8b8f3913ba4f904be1814df78a803cfd4f79d.txt) — SHA-256: fde6ed1e1a3e36fed17b165f2da0ce8773550231c5d7e87cc4ec913fbdd96165; bytes: 18222
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-11b91c06a8611f0bc4afe9dbb26b5b1d93c5f1d8c5fff043a950ac602a6cdfc3.txt) — SHA-256: db095b8d76bc7f57ea2088ac44ece2bb67c9b01ff0e069d99f9af743f1e30831; bytes: 18718
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-15e309a80ebd8bc0203dc0fb987850e2e7d8e1a3fe8ae2d3a60079b9464972a0.txt) — SHA-256: 27c3762f431b87cc91f6bd56884ba906bfe7f9aa765e39d1d70e625c024fa0db; bytes: 31113
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-a65cae35d7983d50aa5222b71ea46b917bcd0f619838bea7a5897aa8e8ab36aa.txt) — SHA-256: 576e4ac6811e5e4ae00eeec4cf5bdb6e4c7f234d786802d545c3729382d2a4e8; bytes: 35340
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-ff012bb7cc16a3083376bd439df34a704e9d956de8f8bf4ab1ea92fde4053f61.txt) — SHA-256: aa9ca6d692ecd9d6fde6d41e92e7ecb341fc7275c05b376712bbfa9d41eac80a; bytes: 37663
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-a76951c6bf989b7806684858212cd397d26a6cf5eba07b5d5509fa1a02ed8ae3.txt) — SHA-256: a5cc548816691ace2efdaaefa33f2682131fb84246d6ed6113635837cbe3c898; bytes: 457316
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-535cc86f1e3697063b6751b4b89ad373f8951b62e69f10d1be033c82ce7f16fd.txt) — SHA-256: 0a3855be8ba631ec874e94e855f044fa296527365a110d7a06c6149ebf26bc70; bytes: 24179
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-e70237375ddd041c956db623a00de9bac6d6bbb01b73e7cc8d527e6716ec512d.txt) — SHA-256: bd1832546af3d772da41e500e3a9ae41a323829f9ca2d50f8106d7a8ba41e313; bytes: 23099
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-7305f07e45c84d3bea9a8e43a29e0fa0f6294072f13aae30d37978d241b1e8d5.txt) — SHA-256: 959b4182ec6bd3a437aa7e7d62e574f49ac593a71ee9a65d76b867ef52a29cfd; bytes: 27529
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-7339eb1980ef8fbfb90b83887551cb25edcbfec7bafd9201e6ccee2a63717f53.txt) — SHA-256: 12475c081376c2b3c854ceee836e663ab1132bb7e0ca6e47c69f7330d09a0d25; bytes: 22332
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-66ac9fc41e487161c52af6a2d0672c60bf724a69405c814b8d0f0b5888bb3745.txt) — SHA-256: 5581a039a234eede541334aa725e18d798a99e0d176cbd6358548550daeaed3d; bytes: 20927
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-5e46339f25287445b3503cc7d8605bb29f7383b81fde3ec84bb72967373c95d7.txt) — SHA-256: b1f769fdd88e5d89705c6d34d7f10ed2c4e813fea3827a2f18314e427ecb91d4; bytes: 17892
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-834e447e659770714b0d40dfcc58ecdd0cf9120ac0b2607aabe41bc8d444053d.txt) — SHA-256: 5439eb4dd791915f70bc23dbafd45e62d6f6b931486356463d21aeba2985565d; bytes: 1681
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-5d98deb22b941f0cbe52501608a8bbe9aecba53053ad6884f79fcf8d97411bad.txt) — SHA-256: 5439eb4dd791915f70bc23dbafd45e62d6f6b931486356463d21aeba2985565d; bytes: 1681
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-6ae122214583ed3ecc07f73cfe50c1ffbd5a1a2b109c934bfff1c27243ec8b99.txt) — SHA-256: f97d99c9a8c652f71d11e8daeab573ec35876485ace6e81df45553295dba955e; bytes: 1856
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-4ac00c266f9be9edba8b6bb53ac773bd6098e45e76dd23ea04c82d7e3dbb5be6.txt) — SHA-256: f97d99c9a8c652f71d11e8daeab573ec35876485ace6e81df45553295dba955e; bytes: 1856
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-91531b0b1295a49f406be487e38eaf217aeccb8148b17f838623f185e4b3d520.txt) — SHA-256: 098f1c3057104179e11e7897f8dd91765c34f9001f8693827d734e26e647b443; bytes: 2453
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-8824f678f9a805396b0f434a6df579e16555a4a0ee934cb425ec8e62bcf19c82.txt) — SHA-256: 098f1c3057104179e11e7897f8dd91765c34f9001f8693827d734e26e647b443; bytes: 2453
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-d32ba787859b6f2e5d6ccf1c73dd98f73d5cfa3513fa2655caa2216d0d459f8f.txt) — SHA-256: efafdeddf63e194b4fe619dc1c2f827ab30addefe8e2e45056695250cb7740ab; bytes: 1792
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-4df036b3b2bcf668353a6f53d50e40ae32a3c3b646f3e67fbcbe4f541e1da73a.txt) — SHA-256: 22abdc6d6605c75578fb0ab8819ab2516b863c1da544ef776b77fceda3e0a571; bytes: 2263
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-23b953f986ab1e4afd033800f9ac4ecf2a9beeda8e1611bebbc804a38046e730.txt) — SHA-256: efafdeddf63e194b4fe619dc1c2f827ab30addefe8e2e45056695250cb7740ab; bytes: 1792
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-862de7136e83a980fa8cea5d6914f8eca5adddb1a162acc00343924e9afa051d.txt) — SHA-256: 22abdc6d6605c75578fb0ab8819ab2516b863c1da544ef776b77fceda3e0a571; bytes: 2263
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-fdb5e765993e7a76194ab2c1bb832cc322e87d289a5bea9798c25fb225d6efd6.txt) — SHA-256: dcf01e984991c4384beeabaac948ad598e7f8692fd34e8cc14222e8a0dda4ad2; bytes: 2463
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-7b88f859df50f368a375e7bd909431cd2320758337c729068f55769c243df726.txt) — SHA-256: dcf01e984991c4384beeabaac948ad598e7f8692fd34e8cc14222e8a0dda4ad2; bytes: 2463
- [Artifact](runs/case1-cpu-r1/artifacts/readable/rankin-744507d1c80d5f25031ab3239d97ce3c2bab0cebe3b234e9ff023fda565621f4.txt) — SHA-256: 844fd0c3bec0b70e53c350ed8474889f8a730a49fa7e917a10ba76a6ab504e7f; bytes: 1241
- [Artifact](runs/case1-cpu-r1/artifacts/readable/screen-9171f977b75618078967213c17e7a892b8a2d81ad7ae1ea2ebca7c8b27ab2b1f.txt) — SHA-256: 11336f6ccbf243bd1d7dc3b719bdb1ee77a7cc07472e61d36ccd78657aa586e2; bytes: 216
- [Artifact](runs/case1-cpu-r1/artifacts/readable/verifi-508a178c7020c17b41484ae468bd32a26efc789bae7d9b3b06e779dbc31110c8.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case1-cpu-r1/artifacts/readable/intent-28bf5bd75689029146983721c45e95b1e2150690893ce045cb1ec78517f92447.txt) — SHA-256: 4188e32b215676e557541b5c333deec82f1dfdd2ad028720eacf0f522112f295; bytes: 3261
- [Artifact](runs/case1-cpu-r1/artifacts/readable/verifi-f480094f6eed10cf9b3a4d7a624762dfb9ff67c84b895b01c73ebb298a57dacd.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case1-cpu-r1/artifacts/readable/requir-4dea3545d0e59abbd4c8e4126fca7f198b6c208399d3cd22089e1fffaa1cf193.txt) — SHA-256: 84e87546a59222368949dd78e570b3a5a3157c452634c58e70970841d221a065; bytes: 4890
- [Artifact](runs/case1-cpu-r1/artifacts/readable/verifi-1be9117482f12290a2df717a1e39703faf13119d188893a836dfad342f51a824.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case1-cpu-r1/artifacts/readable/planne-d9e4887b2e079f98baa4624d837d98a421faa7b4655b89b457b9092f39c675ae.txt) — SHA-256: ce1125e34d6c51808effbee196ae63d3c66af6badb293f994e43361f8a8c7b6c; bytes: 6443

Available observations:

```json
{
  "event_bytes": 22455,
  "event_cursor": 37,
  "event_files": [
    {
      "path": "events/0-16e69398d24d5048bfbec4d6c1ad47f3b1be392dad2801fde9d09d1b30278a4d.json",
      "sha256": "16e69398d24d5048bfbec4d6c1ad47f3b1be392dad2801fde9d09d1b30278a4d",
      "size": 1047
    },
    {
      "path": "events/2-8f00b4f5e22ce8f5affdb21c10f15ba87472454c1818ae9acd7d1a118b2ee15c.json",
      "sha256": "8f00b4f5e22ce8f5affdb21c10f15ba87472454c1818ae9acd7d1a118b2ee15c",
      "size": 3764
    },
    {
      "path": "events/5-a496e21c00972c6116a9517ac106ed154be370119aeb4a86f2ddb1cc4d69e01a.json",
      "sha256": "a496e21c00972c6116a9517ac106ed154be370119aeb4a86f2ddb1cc4d69e01a",
      "size": 1198
    },
    {
      "path": "events/7-09c3dddeebbe22b88912ecbb09c402975dc80648803dbff84dcc1ab99dd9ba8e.json",
      "sha256": "09c3dddeebbe22b88912ecbb09c402975dc80648803dbff84dcc1ab99dd9ba8e",
      "size": 2058
    },
    {
      "path": "events/11-2c41d988ceb6293dac9084d0537ac2494d84428f9c8fe494323a935c09bc62b1.json",
      "sha256": "2c41d988ceb6293dac9084d0537ac2494d84428f9c8fe494323a935c09bc62b1",
      "size": 1189
    },
    {
      "path": "events/13-2eca3a677f8bc6269792d4773af3c3085b2380d17969852164961a7722e9bf2a.json",
      "sha256": "2eca3a677f8bc6269792d4773af3c3085b2380d17969852164961a7722e9bf2a",
      "size": 1611
    },
    {
      "path": "events/16-618775bde796504b143542c93c2ff91f0bb5fc7b132c3fcec9e244286d06aaed.json",
      "sha256": "618775bde796504b143542c93c2ff91f0bb5fc7b132c3fcec9e244286d06aaed",
      "size": 1173
    },
    {
      "path": "events/18-c30fd97039c0f46475a50aa162a501c7593b8d71c9bd0b0188b39ac4c4fd28c0.json",
      "sha256": "c30fd97039c0f46475a50aa162a501c7593b8d71c9bd0b0188b39ac4c4fd28c0",
      "size": 1580
    },
    {
      "path": "events/21-818fe0ad817b6e5fb21da72490897bae10877c2a463aee18bbd9fd6d185f0c30.json",
      "sha256": "818fe0ad817b6e5fb21da72490897bae10877c2a463aee18bbd9fd6d185f0c30",
      "size": 1578
    },
    {
      "path": "events/24-31647e1f32c55f7ee4a3d18d1a49f653bc409e1bcd80b7680726102a7ab8c155.json",
      "sha256": "31647e1f32c55f7ee4a3d18d1a49f653bc409e1bcd80b7680726102a7ab8c155",
      "size": 760
    },
    {
      "path": "events/25-31b3470171a0b49577dbf5f9f2d475187b1f27db206743f4af99fbc2f46d575d.json",
      "sha256": "31b3470171a0b49577dbf5f9f2d475187b1f27db206743f4af99fbc2f46d575d",
      "size": 1175
    },
    {
      "path": "events/27-8c4ddbb47500d3a23c597935b03be3d3e8167e8cb65c2c8f64dbc6e6fb6cd294.json",
      "sha256": "8c4ddbb47500d3a23c597935b03be3d3e8167e8cb65c2c8f64dbc6e6fb6cd294",
      "size": 1618
    },
    {
      "path": "events/30-7b4ea1ef5530f7db1391943f06bc7c18fe84fa4f5c00b5766f6cfd5f007c8780.json",
      "sha256": "7b4ea1ef5530f7db1391943f06bc7c18fe84fa4f5c00b5766f6cfd5f007c8780",
      "size": 1642
    },
    {
      "path": "events/33-17388f1fddf32dd74ba73ea9dbc607efab420b32f2e3491c6932ac3438975bdd.json",
      "sha256": "17388f1fddf32dd74ba73ea9dbc607efab420b32f2e3491c6932ac3438975bdd",
      "size": 2062
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
    "at": "2026-10-23T18:58:43Z",
    "category": "collection_failure",
    "detail": ""
  },
  {
    "at": "2026-10-23T18:59:38Z",
    "category": "collection_failure",
    "detail": ""
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

