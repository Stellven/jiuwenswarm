<!-- ai4r-human-report:1 -->
# Campaign observations

Execution and collection states describe infrastructure, not research correctness.

## Inputs and Setup

Campaign: demo-cpu-paper-20261023-103800

| Case | Repeat | App run | Execution | Collection |
| --- | ---: | --- | --- | --- |
| case1-cpu | 1 | run:7705df93bd904f5d9e37c99b156d29c8 | halted | complete |
| case3-paper | 1 | run:b2f47b0438ab476a9bbee1dc2c8d6c14 | completed | complete |

## Actual Output and Observations

### case1-cpu / repeat 1

Request: request-1c6142b5fd154037934f161b19708d95

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
      "path": "demos-20261023/case1-cpu/provenance.py",
      "sha256": "5badf267d60eaa52770904ced0dfad96c5a57a8e6c87fb3c4e96449e1bcc4b2f",
      "size": 823,
      "upload": false,
      "upload_record": null
    },
    {
      "destination": "runtime-meta.json",
      "kind": "docs",
      "path": "demos-20261023/case1-cpu/runtime-meta.json",
      "sha256": "e6685a1a9f50b8acd1f892fe8518cc8546927f019be2352a7cb7a7235881b706",
      "size": 1265,
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

- [Artifact](runs/case1-cpu-r1/workspace/runtime-environment.json) — SHA-256: 6689bdcd2fa511bc580e0fffa622654a9a95f957ea44bb4d895606e4a7fb5514; bytes: 1642
- [Artifact](runs/case1-cpu-r1/artifacts/originals.zip) — SHA-256: 0419e23fe7c0b40c5c87bdf0cd91dc8aa9f05154271be56c9e3aa5e17a09a50a; bytes: 14758892
- [Artifact](runs/case1-cpu-r1/artifacts/originals.inventory.json) — SHA-256: 693ad0b0b1650a2fb89fda39679b3d9e34a6897319dd370d684c1c19939712cb; bytes: 13586283
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-84efcfdfbfe8017ae55ba14bca4a2b810a7eb418757e8ec4ca474b53b2da0438.txt) — SHA-256: 0f78a1d5220501be4bdb68b00970758a98a6da7d1bbf8ba5a10888382177bcd2; bytes: 19029
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-7edd78fe229a172a35d858af29c679b056b20c51a406bb8f6d160452a832682d.txt) — SHA-256: cc93586a72581534f31e0dccd0b834e0940c118d9130b24e4992838d84a2a4b0; bytes: 18718
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-01c60e61b9852fbd52505028199b2a06b3a2fdb58707d0eb00ac53da882ef0de.txt) — SHA-256: 0243cfb2c9998f3d750bed289dd44b61e2b0f4ffc46cb3e6ab21001ff15087b0; bytes: 28345
- [Artifact](runs/case1-cpu-r1/artifacts/readable/prompt-9cdbad4dbffa02cb58ab5ed7d56c40723fdb9c1bcba1bb6caa34b56a82f8aa74.txt) — SHA-256: 9acd4d6e6a3f1dca1f97c3b4341e25f98f51ffb21aa3b124386e2b3e451900ef; bytes: 33903
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-345db14a09ac1dd4867af95139e78cbc4d5617c2555e1cbfdc24773d61bda050.txt) — SHA-256: 8efd3a251a938cd74dedc353f7dbbf034439be67c0548316c031af2bc760f5f5; bytes: 1588
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-7e52b6b6031c7ac2c2da9399191aaca0357be0cf7014aca787dab6bb602ee637.txt) — SHA-256: 8efd3a251a938cd74dedc353f7dbbf034439be67c0548316c031af2bc760f5f5; bytes: 1588
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-67be983b2c779afca194590801b0dad2730e5871e4e2390b6a2f735d0aea9551.txt) — SHA-256: 10311b93d5aa083b30ac27091a0f0c6ea58049c3aaac90b8dea42a3680380c9b; bytes: 1734
- [Artifact](runs/case1-cpu-r1/artifacts/readable/output-346fc27db6415324c652076a5231cd9ecc99cda8dadc3651f6fbc3f421740061.txt) — SHA-256: 10311b93d5aa083b30ac27091a0f0c6ea58049c3aaac90b8dea42a3680380c9b; bytes: 1734
- [Artifact](runs/case1-cpu-r1/artifacts/readable/verifi-50dddbbe96c04079510b6f93691ea7f5084b40529019e7b86a7b30e69ae070a3.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case1-cpu-r1/artifacts/readable/intent-c81168d585f37a3f1851459154d08d7fda53e99df69a169ca9825298d73a8167.txt) — SHA-256: 4188e32b215676e557541b5c333deec82f1dfdd2ad028720eacf0f522112f295; bytes: 3261
- [Artifact](runs/case1-cpu-r1/artifacts/readable/verifi-64b7b1e8df221f93ac9549d4cd4c3124e64f2de72887a2db5576d61be3c0ad02.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case1-cpu-r1/artifacts/readable/requir-f71db3f01090501b347184db9bb6d5315a8aeaf542867bc7de5d27d59f9b68d4.txt) — SHA-256: 2e85b19cad8cd78538294d511b9c74ae1152aa9b75c26a7c874236d616add2e4; bytes: 4669

Available observations:

```json
{
  "event_bytes": 8396,
  "event_cursor": 11,
  "event_files": [
    {
      "path": "events/0-a486c9e1a4af5629c3c23ce3268472ca07eb0791635cdb13a8744c0f397b125b.json",
      "sha256": "a486c9e1a4af5629c3c23ce3268472ca07eb0791635cdb13a8744c0f397b125b",
      "size": 1047
    },
    {
      "path": "events/2-a5a7809838136a0ad220fd8ad8e4637a5691c1f388348451ea88ffef7f9b4e2c.json",
      "sha256": "a5a7809838136a0ad220fd8ad8e4637a5691c1f388348451ea88ffef7f9b4e2c",
      "size": 3736
    },
    {
      "path": "events/5-267cb3a58560d06057cc4c8c6ae0a02a3fa8238e8e59c0d9fd53530333455fb8.json",
      "sha256": "267cb3a58560d06057cc4c8c6ae0a02a3fa8238e8e59c0d9fd53530333455fb8",
      "size": 1198
    },
    {
      "path": "events/7-d6563f47428d6b601385e8ebdec5144f06b1155263ca32e8a68b492a7df38924.json",
      "sha256": "d6563f47428d6b601385e8ebdec5144f06b1155263ca32e8a68b492a7df38924",
      "size": 1637
    },
    {
      "path": "events/10-bbaed91c203ce656f31a3ef9eaa4d110f736cfd670d66654bbb4367c0d7e7c2a.json",
      "sha256": "bbaed91c203ce656f31a3ef9eaa4d110f736cfd670d66654bbb4367c0d7e7c2a",
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

### case3-paper / repeat 1

Request: request-ad2a783353e04f588b13ae3ae9a1649d

Task:

Using only the attached paper (chunk-recomputation-2610.31019.pdf), summarize its main claims, the evidence for each with section or table references, and the limitations the authors state. Then answer: (1) On how many of the Chinese articles did content-defined chunking fail? (2) What fraction of the embedding workload did fixed-size chunking recompute for Chinese and for English articles? (3) How many revision pairs are in the primary benchmark, and how many articles are in the common-success pool processed by all three chunkers?

Inputs and setup:

```json
{
  "inputs": [
    {
      "destination": "chunk-recomputation-2610.31019.pdf",
      "kind": "docs",
      "path": "demos-20261023/case3-paper/chunk-recomputation-2610.31019.pdf",
      "sha256": "7fcebd072e0a7b128736ae0b30b31dc35aaff471e1766006b2e2881ed0ac1fe9",
      "size": 270399,
      "upload": true,
      "upload_record": {
        "content_sha256": "7fcebd072e0a7b128736ae0b30b31dc35aaff471e1766006b2e2881ed0ac1fe9",
        "deleted_at": null,
        "filename": "chunk-recomputation-2610.31019.pdf",
        "id": "upload:69d007eed376c0be86c82318dc943c3c",
        "kind": "docs",
        "resource_type": "reference_document",
        "schema_version": "1.0.0",
        "scope_id": "local",
        "size_bytes": 270399,
        "status": "uploaded",
        "stored_path": "workspace/input/docs/local/chunk-recomputation-2610.31019.pdf",
        "text_sha256": "61b63b9b3ce68707d758cdfa178d34972a44b31000f27eda56ee3748d83fb107",
        "uploaded_at": "2026-10-23T14:42:12Z",
        "user_id": "account:6c5a319ddb5ca5725f547de5baa97e86"
      }
    },
    {
      "destination": "provenance.py",
      "kind": "docs",
      "path": "demos-20261023/case3-paper/provenance.py",
      "sha256": "5badf267d60eaa52770904ced0dfad96c5a57a8e6c87fb3c4e96449e1bcc4b2f",
      "size": 823,
      "upload": false,
      "upload_record": null
    },
    {
      "destination": "runtime-meta.json",
      "kind": "docs",
      "path": "demos-20261023/case3-paper/runtime-meta.json",
      "sha256": "e6685a1a9f50b8acd1f892fe8518cc8546927f019be2352a7cb7a7235881b706",
      "size": 1265,
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

Execution: completed; collection: complete.

[Saved run record](runs/case3-paper-r1/run_record.json)

- [Artifact](runs/case3-paper-r1/workspace/runtime-environment.json) — SHA-256: 6689bdcd2fa511bc580e0fffa622654a9a95f957ea44bb4d895606e4a7fb5514; bytes: 1642
- [Artifact](runs/case3-paper-r1/artifacts/originals.zip) — SHA-256: 2158e6ccf73e5ccad3d8f5b87b443de9ee22956ac17ddc2e0cf28343361d9851; bytes: 23443405
- [Artifact](runs/case3-paper-r1/artifacts/originals.inventory.json) — SHA-256: b31e4de3a8837ce7eb6b7b695645380be5f81e3f163f36323f26f4f88989c24b; bytes: 20993445
- [Artifact](runs/case3-paper-r1/artifacts/readable/paper_summary.md) — SHA-256: eb43ccdff4bca1f66893b23de94199b40cfb291107e5b9bc7683047ac2654ced; bytes: 8512
- [Artifact](runs/case3-paper-r1/artifacts/readable/sources/document_001.txt) — SHA-256: 61b63b9b3ce68707d758cdfa178d34972a44b31000f27eda56ee3748d83fb107; bytes: 34327
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-6ac00ee2d0c28b60dc7b62e719f65322b6676133d36b16371b0ca60247f9f5d0.txt) — SHA-256: 93f2f0cd73f1027c4f2d7aa29e71389eef0defb35cd58de1cd2a5fa7d5a72d9f; bytes: 18116
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-9491388d9a6044afe9b8f81333d59b582c83ae7ebf065ba81b4993baf794086a.txt) — SHA-256: 31adf52456cce4aa51f7713c6f0cfad25223570440875df8c68d47eeceb77c0a; bytes: 24185
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-618ab222b39a954abc10f4fa55ad53c85d40cac836d344ffdc657a4e69700a7f.txt) — SHA-256: 6e0569aa8c45d5b202da7ef04a50606e37c1e902c60343aeabbd174263968c70; bytes: 17445
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-39c5548e1f461c836335054a9286526431f45d5e062a2c475d408e3d7c3562f0.txt) — SHA-256: 05f65f4312c989e8dba02d39fd3ae757d4b93565ffcaf9201b1004a15c323ad0; bytes: 52582
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-e590a92f7cf979c00dc4760127213538922e4b616f3226682516345c42467f83.txt) — SHA-256: baee4ed1a8b4c9e729d69ee0f0d36430268e43c6742d70dd1bf0165b4a27e73f; bytes: 25448
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-1e47ae879bad18766a0e11f47db64f57be18b6ff144243048549a88775aa9fc2.txt) — SHA-256: 96d4e72e883f6560315ea0d6bfb91dc3b3f5fc73e8983447b30b04d26c58d1b0; bytes: 65923
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-e5469a489e6f0453a84fdcfe16b7e0436688a0e59fa8bf3d70bbe33ebdd1df2a.txt) — SHA-256: d789fd009599c21f9f560ed8ecf0dba59ce6a5cb728f40f922a0eaf39ba131e5; bytes: 24921
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-d20eed3fda608773268fba5d34c8d7e8998e7332d1da6732434cb7ca425f5230.txt) — SHA-256: 60176b5bf29e63074360174ed59975bae0d55c1146e89ba1ff820e638b4d9960; bytes: 452777
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-65be2b4892d63692552dd766d619294c69a4bd07f65311bc821872ec3deca4dd.txt) — SHA-256: a053991ee793360631fc45718d62bdadc405a985ef3f146168aef33b399c4b96; bytes: 59758
- [Artifact](runs/case3-paper-r1/artifacts/readable/prompt-383bf3f74ba599dc127ac215744464b11cde864da8701801f1ae9961651d6851.txt) — SHA-256: 5e2633e9ee917df7a2fe7589d0761dcc1010564099fa804f8a4e34eac18be1d2; bytes: 60725
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-f7ae1bce33241d98d2149609b96eca98f142b848ab2942b89178352c5c166c53.txt) — SHA-256: a88a687a6438e416f603e73d9ea9479c06bcb1786fe31f3c6290ffa562300d91; bytes: 2086
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-114dd99ef0a9ab78b7294c8493e1df1033a211502a8b4f1bdcce39d6c0759002.txt) — SHA-256: 4a8574755e674e2ee70b07cc54b6cda06a28ae249429e0388514774269029da1; bytes: 2690
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-e1cfe2aabe700ae04dc3995d52dcdc78d748572e953f15e8a6adfaeccceefe63.txt) — SHA-256: a88a687a6438e416f603e73d9ea9479c06bcb1786fe31f3c6290ffa562300d91; bytes: 2086
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-c1f267499ff119e7c4a4903335e4be9ee7058ca8c3c22dd59b8d2253fe5cc074.txt) — SHA-256: 4a8574755e674e2ee70b07cc54b6cda06a28ae249429e0388514774269029da1; bytes: 2690
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-9e958308c18213a1cae393f2eb2f9cfc694273c1e02843700cb98d75cdff5913.txt) — SHA-256: ffdea57935be28dd93f0c1e9940b6210945e0a66ed7c81051797d01ee1a808da; bytes: 1565
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-53c64f2bba6c73a9a16a58edbc058a49ebb6820dd1f80b42bc3aedf426239b9c.txt) — SHA-256: ffdea57935be28dd93f0c1e9940b6210945e0a66ed7c81051797d01ee1a808da; bytes: 1565
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-6a8a6224e73aa57acc89c17482e7619f8678fe094d605cc85f48735df3dae23d.txt) — SHA-256: 243ef2785f42f431243415767b5b63dd7a09ecccda9e33cca114290a8ce03f85; bytes: 1620
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-9516fd418107507871d21d1e5955d1d5aa43ab44c877e3cbfbc1849f6af3a458.txt) — SHA-256: 243ef2785f42f431243415767b5b63dd7a09ecccda9e33cca114290a8ce03f85; bytes: 1620
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-91c55d9fd5eb2ed35579f91f1deac57ed806074c17ceac14ff7f01a35c722096.txt) — SHA-256: 40e72aa156d8508af6570ed29a0abfab03c7c6f250c617e36ec0112fce2dd54a; bytes: 2429
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-87e365a635c4521f8bb3be721e3b8f2f1df07beb3006475419d0d5fb1150ce12.txt) — SHA-256: 40e72aa156d8508af6570ed29a0abfab03c7c6f250c617e36ec0112fce2dd54a; bytes: 2429
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-a07697fa4fff9d94c77719e9e0d78a6220f8e532c22fbf01772b4f3b0d349f90.txt) — SHA-256: 4b91370205854b6596674269c5e619ec2792fb7f9acb31b86f43658a37190a66; bytes: 2912
- [Artifact](runs/case3-paper-r1/artifacts/readable/output-86861d9cfe4067e61d1f6170744cf15ed14b0196f757015cc5b2f1c756df20ec.txt) — SHA-256: 4b91370205854b6596674269c5e619ec2792fb7f9acb31b86f43658a37190a66; bytes: 2912
- [Artifact](runs/case3-paper-r1/artifacts/readable/verifi-42b32fbd720d6ff333d09184cadce69f7ce86a45b0d4a9f7505a3b98af07fd94.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case3-paper-r1/artifacts/readable/verifi-c52670d4db555d0cda62e97ddd7ff85a868ac201b4dc8a9424c5dd19661696f0.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case3-paper-r1/artifacts/readable/verifi-adca147cf375ea5ce57747f4a1d14cccca497d056493f5b67ba4c7dfc0b7c50c.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case3-paper-r1/artifacts/readable/intent-2f430f27d777a65fc99807155717abff682ac9815c681eb80d1e90604db392aa.txt) — SHA-256: 4188e32b215676e557541b5c333deec82f1dfdd2ad028720eacf0f522112f295; bytes: 3261
- [Artifact](runs/case3-paper-r1/artifacts/readable/verifi-6dcac2391aedb232e670a49064823d1937749e860125b31141dc21341956cf57.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case3-paper-r1/artifacts/readable/requir-321ee133a72060584002e531df1375b7b20a87540d05634cc5a714a98eabaf90.txt) — SHA-256: 2e85b19cad8cd78538294d511b9c74ae1152aa9b75c26a7c874236d616add2e4; bytes: 4669
- [Artifact](runs/case3-paper-r1/artifacts/readable/verifi-09c8ad58d8db58ebc3aa6645f595f626b98baa4b83ab84cb951498237947adce.txt) — SHA-256: 89018d720c6ce3dffdcd4da1da6af0af39e1e45ee951e4f8bb12b9095d0251c8; bytes: 956
- [Artifact](runs/case3-paper-r1/artifacts/readable/planne-1b91942e96f640fe0e8273338f4d1d51c43dd23f0dcb85002ccbf2eded099b19.txt) — SHA-256: ce1125e34d6c51808effbee196ae63d3c66af6badb293f994e43361f8a8c7b6c; bytes: 6443

Available observations:

```json
{
  "event_bytes": 19287,
  "event_cursor": 32,
  "event_files": [
    {
      "path": "events/0-c7479f31f7809844b222af6cbd3ca00bba94b6b52bc0330307ab8224a69f068c.json",
      "sha256": "c7479f31f7809844b222af6cbd3ca00bba94b6b52bc0330307ab8224a69f068c",
      "size": 1047
    },
    {
      "path": "events/2-03b23272c324f51b3b772e194fd21634f59b401999e74ce8ab000cc0c86a1453.json",
      "sha256": "03b23272c324f51b3b772e194fd21634f59b401999e74ce8ab000cc0c86a1453",
      "size": 3715
    },
    {
      "path": "events/5-69e47f3799b1c6e8db29f951a1ece2a4b18ee23722b0aa2dfa6850d83918c55b.json",
      "sha256": "69e47f3799b1c6e8db29f951a1ece2a4b18ee23722b0aa2dfa6850d83918c55b",
      "size": 1198
    },
    {
      "path": "events/7-8137eb771b0453a9b64d686478f11eac4e00b9f0ba94fe3e5f4e7b8aecc65786.json",
      "sha256": "8137eb771b0453a9b64d686478f11eac4e00b9f0ba94fe3e5f4e7b8aecc65786",
      "size": 2058
    },
    {
      "path": "events/11-a856b9ea7050ee54d3f6b36a0f82a122066db75504c4d83dab3dd11584f4d9ba.json",
      "sha256": "a856b9ea7050ee54d3f6b36a0f82a122066db75504c4d83dab3dd11584f4d9ba",
      "size": 1189
    },
    {
      "path": "events/13-87edd27894f3b81b837f0332f361615a1b9ec40a9139552aa2ea2ca498ca51b4.json",
      "sha256": "87edd27894f3b81b837f0332f361615a1b9ec40a9139552aa2ea2ca498ca51b4",
      "size": 2470
    },
    {
      "path": "events/18-2e38066198548bc12a241cee90865c14576e5739c0f5ef893994fee2fcf56e54.json",
      "sha256": "2e38066198548bc12a241cee90865c14576e5739c0f5ef893994fee2fcf56e54",
      "size": 1173
    },
    {
      "path": "events/20-3fe4c7590f59263eddd8849130635e5b9dfb9d78ab5e60a07f7234d60b713bc9.json",
      "sha256": "3fe4c7590f59263eddd8849130635e5b9dfb9d78ab5e60a07f7234d60b713bc9",
      "size": 1595
    },
    {
      "path": "events/23-7678b18463c740c87cee37e9c52c149bfecea97e75f8b6f83152f0da32071451.json",
      "sha256": "7678b18463c740c87cee37e9c52c149bfecea97e75f8b6f83152f0da32071451",
      "size": 1173
    },
    {
      "path": "events/25-7df070a420bb7c10907aad0df34e738ae21f1e2e8d68c4e33f4638c6d24a3c1d.json",
      "sha256": "7df070a420bb7c10907aad0df34e738ae21f1e2e8d68c4e33f4638c6d24a3c1d",
      "size": 1613
    },
    {
      "path": "events/28-aa9b8f3a02762cd89242db76e41994ac14d59f7879486531f06925e7fc974b53.json",
      "sha256": "aa9b8f3a02762cd89242db76e41994ac14d59f7879486531f06925e7fc974b53",
      "size": 2056
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

<!-- review:case3-paper-r1:assessment -->

<!-- /review -->

#### Evidence references

<!-- review:case3-paper-r1:evidence_references -->

<!-- /review -->

#### Review notes

<!-- review:case3-paper-r1:review_notes -->

<!-- /review -->

