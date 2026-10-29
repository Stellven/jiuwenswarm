"""Browse original Harbor jobs from several controller roots on one local port.

Uses Harbor's installed API and bundled frontend without modifying its package or
job files. Source ordering selects the authoritative copy of duplicate job names.
No launch, delete, upload, authentication, or other mutation API is exposed.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
from urllib.parse import unquote

import httpx
from starlette.responses import HTMLResponse, JSONResponse


BRANDING = r'''<style id="ai4r-bench-branding">
header > .ai4r-bench-header {
  display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  column-gap: 8px;
}
.ai4r-bench-header > :first-child { justify-self: start; }
.ai4r-bench-header > :last-child { justify-self: end; }
#ai4r-bench-title {
  grid-column: 2; grid-row: 1; margin: 0; white-space: nowrap;
  font-size: clamp(13px, 2.4vw, 18px); font-weight: 600; line-height: 1.2;
  letter-spacing: -.02em; text-align: center; pointer-events: none;
}
@media (max-width: 400px) {
  header > .ai4r-bench-header { column-gap: 4px; padding-inline: 8px; }
}
</style><script id="ai4r-bench-branding-script">
(() => {
  const brandingStyle = document.getElementById('ai4r-bench-branding').textContent;
  function brandViewer() {
    // Keep the small overlay intact if native document hydration replaces head.
    if (!document.getElementById('ai4r-bench-branding')) {
      const style = document.createElement('style');
      style.id = 'ai4r-bench-branding';
      style.textContent = brandingStyle;
      document.head.appendChild(style);
    }
    // Native route rendering stays in charge of controls, rows and sort state.
    const header = document.querySelector('header');
    const row = header && header.querySelector(':scope > div');
    if (row && row.querySelector('a[href="/run"]')) {
      row.classList.add('ai4r-bench-header');
      if (!row.querySelector('#ai4r-bench-title')) {
        const title = document.createElement('h1');
        title.id = 'ai4r-bench-title';
        title.textContent = 'AI4R Bench Hub';
        row.insertBefore(title, row.children[1] || null);
      }
    }
    // Change only label text, retaining native column keys and all job data.
    for (const label of document.querySelectorAll('th, [role="columnheader"], label')) {
      const walker = document.createTreeWalker(label, NodeFilter.SHOW_TEXT);
      let text;
      while ((text = walker.nextNode())) {
        if (text.nodeValue.trim() === 'Job Name') {
          text.nodeValue = text.nodeValue.replace('Job Name', 'Test Cases');
        }
      }
    }
  }
  let queued = false;
  new MutationObserver(() => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => { queued = false; brandViewer(); });
  }).observe(document.documentElement, {childList: true, subtree: true, characterData: true});
  brandViewer();
})();
</script>'''


def source_path(value: str) -> Path:
    """Keep deeply nested original artifacts readable on Windows as well."""
    path = Path(value)
    if os.name != "nt":
        return path
    text = str(path.absolute())
    if text.startswith("\\\\?\\"):
        return path
    if text.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + text[2:])
    return Path("\\\\?\\" + text)


class Viewer:
    def __init__(self, config: Path):
        self.config = config
        self.apps = {}

    def discover(self):
        from harbor.viewer.server import create_app
        import harbor.viewer.server as server

        sources, jobs = [], {}
        for source in json.loads(self.config.read_text(encoding="utf-8"))["sources"]:
            root = source_path(source["path"])
            item = dict(source, available=False, jobs=[])
            try:
                if root.is_dir():
                    names = sorted(p.name for p in root.iterdir() if p.is_dir()
                                   and ((p / "config.json").is_file()
                                        or (p / "result.json").is_file()))
                    item.update(available=True, jobs=names)
                    key = str(root)
                    if key not in self.apps:
                        self.apps[key] = create_app(root, mode="jobs",
                            static_dir=Path(server.__file__).parent / "static")
                    for name in names:
                        jobs.setdefault(name, key)
            except OSError as exc:
                item["error"] = type(exc).__name__
            sources.append(item)
        return sources, jobs

    async def fetch(self, key, path, params=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.apps[key]),
                                     base_url="http://harbor-local") as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def summaries(self, request, jobs):
        params = [(k, v) for k, v in request.query_params.multi_items()
                  if k not in {"page", "page_size"}]

        async def read_root(key):
            result, index = [], 1
            while True:
                data = await self.fetch(key, "/api/jobs", params +
                                        [("page", str(index)), ("page_size", "100")])
                result.extend(item for item in data["items"] if jobs.get(item["name"]) == key)
                if index >= data["total_pages"]:
                    return result
                index += 1

        groups = await asyncio.gather(*(read_root(key) for key in set(jobs.values())))
        return sorted((item for group in groups for item in group),
                      key=lambda item: item.get("started_at") or "", reverse=True)

    async def list_jobs(self, request, jobs):
        try:
            page = int(request.query_params.get("page", 1))
            size = int(request.query_params.get("page_size", 100))
            if page < 1 or not 1 <= size <= 100:
                raise ValueError
        except ValueError:
            return JSONResponse({"detail": "Invalid page or page_size"}, status_code=422)
        items = await self.summaries(request, jobs)
        total = len(items)
        return JSONResponse({"items": items[(page-1)*size:page*size], "total": total,
                             "page": page, "page_size": size,
                             "total_pages": math.ceil(total/size)})

    async def __call__(self, scope, receive, send):
        from starlette.requests import Request

        if scope["type"] == "lifespan":
            while True:
                event = await receive()
                if event["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif event["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        request = Request(scope, receive)
        path = request.url.path
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            response = JSONResponse({"detail": "This viewer only browses persisted results."}, 405)
        elif (path.endswith("/stream") or path.startswith("/auth/")
              or (path.startswith("/api/auth/") and path != "/api/auth/status")):
            response = JSONResponse({"detail": "Unavailable in browse-only mode."}, 403)
        else:
            sources, jobs = self.discover()
            if path == "/viewer/sources":
                response = JSONResponse({"mode": "browse_only", "sources": sources,
                    "note": "Original means filesystem access, not a running trial. "
                            "Harbor timestamps report recorded job state; archives are retained history."})
            elif path == "/api/config":
                response = JSONResponse({"folder": "Configured original Harbor job roots",
                                         "mode": "jobs", "environments": [], "browse_only": True})
            elif path == "/api/jobs":
                response = await self.list_jobs(request, jobs)
            elif path == "/api/jobs/filters":
                # Derive filters from the same deduplicated native summaries.
                query_scope = dict(scope, query_string=b"page=1&page_size=100")
                items = await self.summaries(Request(query_scope), jobs)
                counts = {field: Counter() for field in ("agents", "providers", "models")}
                for item in items:
                    for field, values in counts.items():
                        values.update(item[field])
                response = JSONResponse({field: [{"value": value, "count": count}
                    for value, count in sorted(values.items())] for field, values in counts.items()})
            elif path == "/api/compare":
                grouped = defaultdict(list)
                for name in request.query_params.getlist("job"):
                    if name not in jobs:
                        response = JSONResponse({"detail": "Job not found"}, 404)
                        break
                    grouped[jobs[name]].append(("job", name))
                else:
                    parts = await asyncio.gather(*(self.fetch(key, path, params)
                                                   for key, params in grouped.items()))
                    tasks, agents, cells = {}, {}, {}
                    for part in parts:
                        tasks.update((t["key"], t) for t in part["tasks"])
                        agents.update((a["key"], a) for a in part["agent_models"])
                        for key, value in part["cells"].items():
                            cells.setdefault(key, {}).update(value)
                    response = JSONResponse({"tasks": list(tasks.values()),
                        "agent_models": list(agents.values()), "cells": cells})
            elif path.startswith("/api/jobs/"):
                name = unquote(path.split("/", 4)[3])
                key = jobs.get(name)
                if key is None:
                    response = JSONResponse({"detail": "Job not found"}, 404)
                else:
                    await self.apps[key](scope, receive, send)
                    return
            elif not self.apps:
                response = JSONResponse({"detail": "No configured job source is accessible",
                                         "sources": sources}, 503)
            elif (not path.startswith(("/api/", "/assets/", "/fonts/"))
                  and path not in {"/favicon.ico", "/favicon.svg", "/docs", "/openapi.json"}):
                import harbor.viewer.server as server
                document = (Path(server.__file__).parent / "static" / "index.html").read_text()
                notice = ('<aside style="position:fixed;bottom:0;left:0;right:0;z-index:9999;'
                    'background:#17212f;color:#fff;padding:8px 16px;font:12px/1.5 system-ui;'
                    'border-top:1px solid #8795a8">Browse only · Persisted Harbor results. '
                    'Trial completion and integration rewards do not establish scientific success. '
                    'Inspect named metrics and verifier output. '
                    '<a href="/viewer/sources" style="color:#9fd6ff">Sources</a></aside>')
                response = HTMLResponse(document.replace("</body>", BRANDING + notice + "</body>"))
            else:
                await next(iter(self.apps.values()))(scope, receive, send)
                return
        await response(scope, receive, send)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    import uvicorn
    # Deliberately fixed: the app retains 127.0.0.1:5175, with no public bind.
    uvicorn.run(Viewer(args.config.resolve()), host="127.0.0.2", port=5175,
                log_level="info", access_log=False)


if __name__ == "__main__":
    main()
