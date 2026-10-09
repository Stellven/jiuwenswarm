import { copyFileSync, mkdirSync } from 'node:fs';
mkdirSync('dist', { recursive: true });
for (const name of ['index.html', 'style.css', 'theme.css']) copyFileSync(name, `dist/${name}`);
