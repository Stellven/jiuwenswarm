# Project-owned Spec Kit state

| Location | Authority |
| --- | --- |
| memory/constitution.md | This project's development principles |
| templates/overrides/ | Optional project-specific differences; highest priority; shared defaults live in the plugin |
| init-options.json | Existing feature-numbering settings and historical initialization options |
| feature.json, when present | Ignored per-checkout feature pointer; not a task lock |

Shared skills, scripts, workflows and core templates are maintained once in the [Codex plugin](../plugins/spec-kit/README.md). Do not recreate a parallel project-local vendor installation. The plugin resolver retains project overrides, presets/extensions and legacy core-template compatibility, then uses its bundled defaults.

Select the registered feature with SPECIFY_FEATURE_DIRECTORY, or explicitly select this project with SPECIFY_INIT_DIR when running from elsewhere. See [project workflow](../docs/code/SPEC_KIT_WORKFLOW.md). Existing initialization/installation metadata is historical; current plugin version provenance is plugins/spec-kit/upstream.json.
