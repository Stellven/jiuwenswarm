# One integrated AI4R

The goal is one application and one chat entry point. A user uploads the relevant files, describes the task, and receives the result in the same conversation. Separate paper-summary and experiment versions are not the final product.

## What changed

- Both task families now belong to the same installed Capsule library and protected configuration.
- Every normal chat request enters the existing Intent and Requirements Compiler. The shared Planner reads the accepted Research Brief and chooses the supported paper-summary or classification-experiment graph. There is no port switch or keyword router.
- A paper summary needs the qualified uploaded PDF. It does not require classification data, a Builder or a scientific scoring environment. The old global experiment-readiness check no longer blocks this task.
- A classification experiment still requires its dataset, approved execution environment and protected hidden-label scorer. Those scientific execution checks remain enforced.
- The integrated app disables the direct-Codex chat option, including stale browser selections, so normal messages use the AI4R backend.
- Selected Capsules retain model routing, deterministic checks, declaration/output-only verifiers and committed gates. Both task families return through the existing chat and delivery path.

## Deployment and use

The final application uses port 5175. Existing accounts, conversations, uploaded files and imported experiment resources are retained. Earlier standalone instances are historical state, not separate final products.

The integrated version is running on port 5175. Authenticated readiness and workflow-status requests both returned HTTP 200 with `ready=true`; the workflow is configured and has no reported diagnostics. Its single library exposes 13 active, eligible Capsules, including the shared Planner and both task families. Client defaults confirm planned AI4R execution and direct chat disabled.

The six existing storage volumes and user account were preserved. The previous run record remains, and the imported dataset references and hidden-label scoring configuration are unchanged. Private labels and generator contents were not inspected or sent to a model during integration.

A WSL shutdown stopped the first deployment. The launcher now automatically maintains its owned, hidden WSL background process during both resume and activation, so a separate visible WSL terminal is not required.

Open the same app from Windows PowerShell:

```powershell
$helper = "$env:LOCALAPPDATA\AI4Research\runtime\poc-clean-isolation.py"
python $helper resume
if ($LASTEXITCODE -eq 0) { python $helper open }
```

For summarization, start a conversation, upload a readable PDF, and ask to summarize it. For a classification experiment, use the imported public dataset, attach the neutral project document and describe the experiment. Keep private labels and generator files out of chat.

## Confirmed and still unconfirmed

Changed Python sources parsed successfully, and the updated Capsule schemas/catalogs were constructed. The running app's authenticated configuration, readiness, shared library and chat defaults were checked. No test campaign or new model-backed research request was submitted. These startup observations do not establish that both task families have completed end to end under the new configuration.

This integrates the two implemented task families. It does not add debugging, arbitrary ML experiments or other new task implementations.
