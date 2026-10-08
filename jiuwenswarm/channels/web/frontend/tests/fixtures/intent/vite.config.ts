import { defineConfig, mergeConfig } from 'vite';
import path from 'node:path';
import nativeConfig from '../../../vite.config';

export default mergeConfig(
  nativeConfig,
  defineConfig({
    build: {
      outDir: 'dist/intent-browser',
      rollupOptions: { input: path.resolve(__dirname, 'index.html') },
    },
  }),
);
