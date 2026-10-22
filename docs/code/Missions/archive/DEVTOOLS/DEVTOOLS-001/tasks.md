# Tasks: DEVTOOLS-001 - Spec Kit Codex plugin
**TASK**: [TASK](TASK.md) | **Spec / Plan revisions**: r3 / r3
**Feature directory**: docs/code/Missions/DEVTOOLS/DEVTOOLS-001/

## Work Items
### Foundation / shared definitions
- [x] T001 [US1] Inspect installed resources, repository rules, native Codex commands and official packaging documentation; capture missing links and unrelated dirty-file hashes.
### Block B01 - Plugin
- [x] T002 [US1] Move vendor capabilities into plugins/spec-kit and adapt script/template paths; B01, AC-002.
- [x] T003 [US1] Verify a relocated package with real isolated PowerShell fixtures; V01.
### Block B02 - Document organization
- [x] T004 [US1] Move templates/examples/snapshots, flatten current guides and repair incoming references; B02, AC-001/003.
- [x] T005 [US1] Check live local links, preserved hashes and whitespace; V02.
### Connected boundaries and system
- [x] T006 [US1] Register and install the package with native Codex commands, inspect installed results and retain actual evidence; B03, V03, AC-002.
### Task hierarchy correction
- [x] T007 [US1] Place the real task tree beneath docs/code/Missions; rebase moved documents and incoming references without changing other content; B02, AC-001/003.
- [x] T008 [US1] Revalidate the task tree, links/anchors, source-file bytes and preservation of non-path text; V02.

### Integrated TASKS/TASK workflow
- [x] T009 [US1] Promote reusable templates and integrate registration with all native commands; colocate existing project records in the user-specified Missions task folders; B01/B02, AC-004.
- [x] T010 [US1] Validate relocated resolution, override precedence and existing-record preservation, repair navigation and refresh installation; V01-V03, AC-001/002/003/004.

### Plugin icon
- [x] T011 [US1] Configure the user-selected upstream Spec Kit logo as composerIcon and logo, sharing assets/icon.webp; refresh to 1.1.1 and verify dimensions, manifest paths and cache byte equality; B01/B03, AC-002.

- [x] T012 [US1] Configure all twelve skill icon interfaces to share the original plugin asset; install 1.1.2 and verify actual Codex skills/list metadata and cache equality; B01/B03, AC-002.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B02 | T004/T007/T009 | V02 / T005/T008/T010 | PASS | [Integrated workflow run](evidence/RUN-20261005-03.md) | TASKS at program level; all four task files together; fictional example removed |
| [AC-002](spec.md) | B01/B03 | T002/T006/T009 | V01/V03 / T003/T010 | PASS | [Integrated workflow run](evidence/RUN-20261005-03.md) / plugin 1.1.0 | Eight real-helper tests; updated native installation and matching cache |
| [AC-003](spec.md) | B02/B03 | T007/T009 | V02 / T008/T010 | PASS | [Integrated workflow run](evidence/RUN-20261005-03.md) | Active links and protected source/evidence hashes verified |
| [AC-004](spec.md) | B01/B02/B03 | T009 | V01-V03 / T010 | PASS | [Integrated workflow run](evidence/RUN-20261005-03.md) | Reusable task design is packaged; defaults/overrides, registered native paths and preservation verified |

## Dependency Order and Execution Notes
T001 precedes migration. T003 follows T002; T005 follows T004. Install after package and integration checks. No subagents, product changes or commits.

## Current Verification Conclusion
- Candidate identity: base 697670e5b4b113645e9296e28ddc19e3a609dada plus working tree; no commit requested.
- Required work complete: Yes, including T009/T010 and the Missions layout.
- Required AC/check coverage: Four ACs and three verification procedures passed with recorded observations.
- Conclusion: VERIFIED for plugin 1.1.0 and the requested physical task structure; natural-language new-chat invocation is not claimed.
- Remaining limitations: A new conversation is needed to discover installed skills; no new-chat UI interaction or product-runtime acceptance is claimed. Concurrent unrelated work is preserved, including the user's confirmed PRD-file removal.

## Evidence Invalidation
Any later package/helper/manifest change requires rerunning affected checks and refreshing the native installed plugin. Historical snapshots remain archival evidence, not current release claims.

### Icon-only update: 1.1.1
Upstream v1.0.12 logo_large.webp is stored once as assets/icon.webp (1080 x 1080, 46884 bytes). Native installation succeeded; all 38 cache files match source. The only package changes since RUN-20261005-03 are the icon, interface/version metadata and asset provenance, so prior helper/template/skill behavior evidence is reused. Client rendering of the configured icon has not been observed in this session. No product or task-generation behavior changed.

### Skill-list icon correction: 1.1.2
Added agents/openai.yaml to all twelve skills, with icon_small/icon_large resolving ../../assets/icon.webp. The original asset is stored once. A local Codex app-server initialize + skills/list(forceReload=true) request returned the installed 1.1.2 asset path for both icons of every Spec Kit skill. All 50 installed package files match source. UI rendering still requires the client to refresh; no model call or task-generation behavior change occurred.

### Desktop picker limitation confirmed
After the user reported unchanged icons, the installed desktop app 26.930.2377 frontend was inspected read-only. Its composer skill picker maps each skill to Icon=eR(galleryKind); eR returns predefined gallery icons or the generic cube, without consulting interface.iconSmall/iconLarge. The same desktop app-server binary (0.159.0-alpha.12.1) successfully resolves all twelve configured icon paths. WebP is also supported by the general icon renderer. Therefore metadata/path/format configuration is valid, but this picker does not render custom skill icons in this client build. Earlier advice to refresh alone was insufficient; no client binary was modified and no further icon-format changes were made.
