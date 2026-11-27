import { copyFile, mkdir, mkdtemp, rename, rm } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { build } from 'vite';
import svgr from 'vite-plugin-svgr';

const output = process.argv[2];
if (!output) throw new Error('Usage: npm run build:factory-static -- <output-folder>');

// These dependency strings are diagnostics and disabled attribution, separate from UI data.
const dependencyLinks = new Map([
  ['https://reactjs.org/docs/error-decoder.html?invariant=', 'React invariant '],
  ['https://locize.com', ''],
  ['https://www.i18next.com/translation-function/formatting', ''],
  ['https://reactflow.dev?utm_source=attribution', '#'],
  ['https://github.com/syntax-tree/hast-util-to-jsx-runtime', 'the HTML-to-JSX documentation'],
  ['https://github.com/remarkjs/react-markdown/blob/main/changelog.md', 'the Markdown changelog'],
  ['File URL host must be "localhost" or empty', 'File URL host must be local or empty'],
]);

const offlineAssets = {
  name: 'factory-static-offline-assets',
  generateBundle(_options, bundle) {
    for (const asset of Object.values(bundle)) {
      if (asset.type === 'chunk') {
        for (const [from, to] of dependencyLinks) asset.code = asset.code.replaceAll(from, to);
      }
      const source = asset.type === 'chunk' ? asset.code : asset.source;
      if (typeof source !== 'string') continue;
      const hosts = [...source.matchAll(/(?:https?|wss?):\/\/([a-z0-9.-]+)/gi)]
        .filter(([, host]) => host !== 'www.w3.org') // SVG and HTML namespace identifiers.
        .map(([, host]) => host);
      if (hosts.length) throw new Error(`External URL in ${asset.fileName}: ${[...new Set(hosts)].join(', ')}`);
    }
  },
};

const root = fileURLToPath(new URL('../', import.meta.url));
const destination = resolve(output);
await mkdir(dirname(destination), { recursive: true });
const staging = await mkdtemp(join(dirname(destination), '.static-factory-'));
try {
  const assets = join(staging, 'assets');
  await build({
    root,
    configFile: false,
    publicDir: false,
    envFile: false,
    base: './',
    define: { __MUSE_STATIC_BUILD__: true },
    plugins: [react(), svgr(), offlineAssets],
    resolve: {
      alias: [
        { find: /^\/logo\.svg$/, replacement: join(root, 'public/logo.svg') },
        { find: '@', replacement: join(root, 'src') },
      ],
    },
    build: {
      target: 'chrome107',
      outDir: assets,
      emptyOutDir: true,
      // A classic bundle works under file:// without module loading or fetch.
      cssCodeSplit: false,
      modulePreload: false,
      rollupOptions: {
        input: join(root, 'src/staticFactory.tsx'),
        output: {
          format: 'iife',
          inlineDynamicImports: true,
          entryFileNames: 'factory.js',
          assetFileNames(asset) {
            if (asset.name === 'style.css') return 'factory.css';
            if (asset.name === 'logo.svg') return 'logo.svg';
            return '[name]-[hash][extname]';
          },
        },
      },
    },
  });
  await mkdir(join(destination, 'assets'), { recursive: true });
  const ready = join(destination, 'assets/factory-build');
  await rm(ready, { recursive: true, force: true });
  await rename(assets, ready);
  await copyFile(join(root, 'static-factory.html'), join(destination, 'index.html'));
} finally {
  await rm(staging, { recursive: true, force: true });
}
