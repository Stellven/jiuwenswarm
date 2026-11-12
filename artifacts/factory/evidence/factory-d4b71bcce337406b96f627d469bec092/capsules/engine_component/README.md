# Expert fill thread names

This passive capsule packages the observability-only 09-thread-names.patch.
It adds Linux pthread names xfill-<worker index> to the expert-fill workers.
It makes no measured speed, activation, or quality claim. component.yaml is
validated separately by factory/schemas/component.schema.json.

Base: llama.cpp cf34d311332e362198f0a410c466d1e940287d02 plus combined patches
01–08 (om11), pre-integration checkout e14b87603. Both patch files are copied
here; SHA-256 values are in component.yaml. The combined patch is provenance
and a reverse-check reference; do not apply it again to pre-integration source.

Scope: Jetson Orin aarch64 sm_87, qwen35moe expert-fill path, any dtype.
Configuration is copied from J-OM11's pg8 arm. On a real decode run, inspect
owned process threads for xfill-* and require every requested effective value.
A CPU Granite probe verifies config parsing only, not worker engagement.
Correctness requires greedy stdout byte identity against om11 under the
immutable qwen36-greedy-v1 contract. No such live verification was performed
by packaging this capsule. Roll back by rebuilding the pre-integration commit
or using campaign/llamacpp:jetson-up1108-om11.

Source material: siminfeng/cc/mmap_advice/patches/09-thread-names.patch and
combined-01-02-03-04-05-06-07-08.patch (copied without changes).
