# Controlled native installation

The metadata-only `jiuwenswarm` wheel depends on the identical
`workswarm[codex,tui]` version. It preserves the native distribution metadata,
entrypoints and original pinned VCS requirements. It is not published by this
workflow.

The application build puts the frozen Node22 TUI `dist`, `package.json` and
pruned locked production `node_modules` tree into the native wheel before
installation. `scripts/research_offline_assets.py` checks every wheel member,
RECORD digest, native base requirement and entrypoint, plus exact correspondence
with the generated TUI input tree. It retains all shipped Koffi platform assets;
generated JS is not represented as original TypeScript source. The emitted
`ai4r-wheel-assets.json` is package-representation evidence only.

This does not yet supply the complete offline Python runtime/build closure.
`pip install --no-index --find-links <wheelhouse> jiuwenswarm` still needs the
original pinned OpenJiuwen and transitive IntelliRouter VCS sources, separate
hash-pinned build tools and all selected runtime wheels. An installed app venv
does not substitute for those artifacts. The required complete producer and
empty-venv positive/negative installation qualification remain incomplete until
actual bounded installation succeeds with network denied and original metadata
preserved. Normal application startup does not install dependencies.

Audit a delivered wheel directory without importing product code:

```sh
python scripts/research_offline_assets.py --wheelhouse /usr/local/share/ai4r-wheels \
  --project /frozen/pyproject.toml --lock /frozen/uv.lock \
  --output /owned/wheel-audit.json
```

Supply `--generated-root` only with the exact frozen build-stage TUI directory
to additionally compare every generated file. The final image contains the
build-stage audit at `/usr/local/share/ai4r-wheel-assets.json`; independent image
closure and current-candidate checks remain separate requirements.
