// esbuild-wasm preload: intercept require('esbuild') -> esbuild-wasm
// This ensures all esbuild file reads go through Node.js (the virtualization layer)
// instead of the native Go binary (which reads raw compressed bytes).

import { createRequire } from 'node:module';
const _require = createRequire(import.meta.url);

// Override esbuild in module cache before Vite loads it
const esbuildWasm = await import('esbuild-wasm');
await esbuildWasm.initialize({
  wasmURL: new URL('./node_modules/esbuild-wasm/esbuild.wasm', import.meta.url).href,
});

// Monkey-patch: redirect all 'esbuild' imports to our WASM version
// We do this by modifying the Node.js module resolution
const Module = _require('module');
const origResolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, isMain, options) {
  if (request === 'esbuild' || request.endsWith('/esbuild')) {
    // Return esbuild-wasm's main entry
    return origResolve.call(this, 'esbuild-wasm', parent, isMain, options);
  }
  return origResolve.call(this, request, parent, isMain, options);
};

console.log('[esbuild-preload] esbuild -> esbuild-wasm override active');