# Four paper-summary comparisons

These locally authored synthetic notes target the actual installed
`urn:ai4r:paper-summary:1.0.0` output shape: clean numerical control; conflicting
abstract/body results; an embedded untrusted instruction; and a proposal without
measured results. Each is a small original UTF-8 Markdown document suitable for
the existing public local-document intake. They are not scientific evidence.

`python -m benchmarks.harbor_suite.value_paper_cases --output NEW_DIRECTORY`
freezes source bytes, public tasks, the installed output schema with its Ref
definition inlined, and competent ordinary native skill/citation-helper assets.
Private finite scoring criteria are kept in a separate private directory. Do not
copy that directory into the native agent's workspace. The original 80-case bank
is unchanged. All four cases initially remain `not_run`.

Native skills and the actual summary carrier can produce the same full summary
contract. Actual product brief/document/source binding IDs may differ; the
independent content scorer does not penalize those identifiers. It verifies
exact quote equality, original Unicode offsets, pages, citation links, expected
facts and visible uncertainty against the original document bytes. It separately
checks readable Markdown delivery against the accepted summary. This is bounded
fixture grading, not an unrestricted semantic truth oracle or admission check.

Use `cases()`, `public_schema()`, `freeze()`, `grade(case, summary)` and
`grade_delivery(summary, report_bytes_or_text)`. Grade the original structured
summary output, not a reconstruction from a prose report. The frozen documents
have no form-feed separators and count as one canonical page. The public generic
citation helper also handles form-feed-separated multi-page text and Unicode.

Use **`request_text(case)` identically in both arms**. Version 2 includes the full
public output schema, exact source filename/hash, document ID, original canonical
page map and Unicode coordinate convention inline, so the compiler need not infer
an omitted schema from a reference to a nonexistent attachment. Upload the source
under the stated filename. `freeze()` saves this text as `request.txt` and records
its hash separately from the task hash. It includes no private grading criteria
or fixture-generated brief/documents binding IDs; product execution uses actual
host bindings. Earlier frozen version 1 directories remain immutable evidence of
the incomplete-request attempt.

## PDF transport required by actual paper planning

The product accepts Markdown intake, but its protected paper-summary planner
requires the upload filename to end in `.pdf`. Use `freeze_pdf(destination,
generator_python=...)` or `--pdf --generator-python ...` for real comparisons.
Reportlab is an explicit optional dependency in that generator interpreter.
Extraction always calls the actual `jiuwenswarm.research.intake.extract_document`
using the current product Python and pinned pdfplumber 0.11.9. It never substitutes
a generator-side parser or assumes the Markdown offsets survive PDF rendering.

Version 3 retains original logical Markdown, generated PDF, original PDF hash,
canonical text capture/hash, and generator/extractor source hashes. No generated
PDF binaries belong in Git. `load_pdf_cases(directory)` verifies frozen hashes
and returns cases whose source text, refs, page maps and citation grader all use
the exact product canonical extraction. It preserves the unchanged fact criteria
and the original logical source separately. Use `request_text()` on these adapted
cases, not the earlier Markdown cases, identically across both arms.

Upload only the case PDF into product docs intake. Give the native arm the same
PDF plus canonical.txt, public task/schema/request and native skill/helper. The
canonical text is the same material the product's paper carrier receives through
its local document buffer. Never expose `private/` grading criteria. Both arms
remain unmeasured until real runs; generating/extracting PDFs makes no model calls.

The PDF transport test optionally accepts `AI4R_TEST_PDF_GENERATOR_PYTHON` when
reportlab lives in a separate bundled interpreter. It regenerates temporary PDFs,
re-extracts them with the actual product intake, exercises the real carrier with
scripted replies against the adapted independent scorer, and rejects hash drift.

The product's summary model reply authors five sections and supplied evidence
IDs. The actual carrier mechanically copies exact quotations and coordinates
into the published summary; native output independently supplies the same public
fields using ordinary tools. Delivery can use the actual deterministic paper
renderer. No E3 invocation, evidence-aware pilot availability or gate acceptance
is inferred by these fixtures. Actual E1 execution still needs the existing
admitted plan, qualified intake, compatible resources and original run evidence.

Tests execute the actual summary carrier and delivery renderer with scripted
replies and mutate facts, citations and missing-evidence responses to verify the
independent scorer. These offline tests make zero model calls and provide no
measured agent-quality result. A real comparative run must retain every raw
output, failure, cost observation and original source selected by each arm.
