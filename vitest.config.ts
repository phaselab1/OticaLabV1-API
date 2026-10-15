import swc from 'unplugin-swc';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    root: './',
    alias: {
      '@/': new URL('./src/', import.meta.url).pathname,
    },
  },
  plugins: [
    swc.vite({
      module: { type: 'es6' },
    }),
  ],
});

