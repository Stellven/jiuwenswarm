# External dataset manual flow

These files contain instructions only. No dataset, generation seed, labels, model run or validation result has been produced here.

Clean 5175 is running with fresh chat/input/research state and the existing subscription login. Until you import an external dataset, research execution is deliberately unavailable. The current settings page may describe this generically as unavailable Builder/isolation resources. That is not a completed data import or a research result. The earlier 5175 volumes/results are preserved, and 5173/5174 remain unchanged.

1. Give [GENERATE_DATASET_PROMPT.txt](GENERATE_DATASET_PROMPT.txt) to a separate AI with file-generation tools. Download its archive and extract its `public/` and `private/` directories into `docs/code/Missions/M1/source/QA/clean_dataset/`. The private directory is Git-ignored; never upload it to the AI4Research chat.
2. Review the public/private file separation. Do not reformat `public/data.json` after its digest has been captured. The private holdout must join its exact bytes and every public test ID.
3. Run the import command below in PowerShell from the repository root. The installed helper privately copies holdout labels into a separate root-protected native folder, captures public data and exact hash pins, and guards configuration activation before restarting only the clean 5175 instance. The Windows QA directory is not mounted into the app. Only public data enters worker/model inputs; private labels, generation records and code remain outside every worker/model mount. Git-ignore is not the runtime privacy boundary. Do not substitute ordinary chat uploads or write files into an active container.
4. Open the clean app using the command below. Upload only `public/project.md` as the neutral document, then paste [RESEARCH_REQUEST.txt](RESEARCH_REQUEST.txt). The importer already supplies public `data.json` to the workflow; you do not need to attach it again. Do not upload the full archive, `private/holdout.json`, generator, seed or oracle.
5. Observe the genuine Compiler → Planner → research Capsules → trusted scoring → Evaluation → Delivery path. Keep the original outcome and evidence even if improvement fails. Check the accepted report/history and authorized evidence download through the same native session.

Import the externally generated files:

```powershell
$bundle = Join-Path (Get-Location) 'docs/code/Missions/M1/source/QA/clean_dataset'
python "$env:LOCALAPPDATA\AI4Research\runtime\poc-clean-isolation.py" import-dataset --public-dataset (Join-Path $bundle 'public/data.json') --private-holdout (Join-Path $bundle 'private/holdout.json')
```

Open the authenticated app in your normal browser without printing its access credential:

```powershell
python "$env:LOCALAPPDATA\AI4Research\runtime\poc-clean-isolation.py" open
```

After a computer shutdown, start Docker/WSL first, then resume the captured app and open it. This preserves its configuration and data; it does not start a research request:

```powershell
$helper = Join-Path $env:LOCALAPPDATA 'AI4Research/runtime/poc-clean-isolation.py'
python $helper resume
python $helper open
```

The helper is installed on this machine. Clean startup and browser opening succeeded; resume on the already-running instance returned `already_running`. An actual external-data import, scientific run and restart after a real shutdown remain unperformed: you will supply those files and run the task yourself. The command reads existing external files; it does not generate a dataset. The operational helper lives outside the repository. Preserve the private generation record and generator separately; neither is an importer argument or a chat upload.

The recommended dataset is 256 training rows, 512 unseen test rows and four numeric features, with compact public JSON preferably below 100 KB. The generator prompt defines the exact supported string-label formats. Execution seed 42 is fixed by the research request; the external generation seed stays private.

Format validity alone does not establish unseen-data fairness, scientific success, protected custody or full product acceptance. Those remain pending until the user supplies files, the protected importer and clean runtime are ready, and the actual run supplies attributable results. Existing QA `output_a` and `output_b` artifacts are unrelated and unchanged.
