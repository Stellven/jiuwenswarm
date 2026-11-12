# Pruned factory build intermediates (2026-11-12T01:37:16Z)

Kept: build-record.json, buildx-metadata.json, build.stdout, prep.json, logs (also ingested in the factory store). Images remain loaded in Docker.

| attempt | removed | sha256 (archive) | bytes |
|---|---|---|---|
| 351b2550 (attempt 1, historical; image factory/llamacpp:aeaa9acc-thread-names-1) | engine-image.docker.tar, build/ (staged tree) | 2ca616c1cb90d5112fbe4803bad55de9a294cfb07d7ac433f441ee8cc11f9c4d | 1392989184 |
| 3216f109 (attempt 2, accepted) | build/ (staged tree) only; archive KEPT for handoff | 3da83cf9adf45a2086ae4ab60144a8780c0ff29bd758dc04b444ae888bf83c24 (kept) | 1392989184 |
| aae86e0c (operator live-jobs build; image factory/llamacpp:livejobs-1) | engine-image.docker.tar, build/ | 1ce43d56c18204929153d56d1974246c5d5a1c7b1524da509d03415cc1593487 | 1392989184 |
| c440203a (operator live-jobs cancel demo; cancelled while compiling) | whole partial attempt dir (823M; no image produced) | n/a | n/a |
