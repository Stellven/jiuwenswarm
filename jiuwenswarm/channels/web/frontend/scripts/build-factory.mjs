import { build } from 'esbuild';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = process.argv[2];
if (!out) throw new Error('Supply a deployment output directory outside the source tree');
const destination = path.resolve(out);
await mkdir(destination, { recursive: true });
await build({
  entryPoints: [path.join(root, 'src/factory.tsx')], bundle: true, minify: true,
  jsx: 'automatic', define: { 'process.env.NODE_ENV': '"production"' },
  outfile: path.join(destination, 'main.js'),
});
await writeFile(path.join(destination, 'index.html'), `<!doctype html>
<html lang="en" data-theme="default" data-color-mode="light"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Native CC Software Factory</title><link rel="stylesheet" href="/main.css">
</head><body style="margin:0"><div id="root"></div><script src="/main.js"></script></body></html>`);
