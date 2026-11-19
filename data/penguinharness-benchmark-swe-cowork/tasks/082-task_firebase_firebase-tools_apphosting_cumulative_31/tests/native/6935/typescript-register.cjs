"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const ts = require("typescript");

// Prefix validation starts a fresh Node process for every node. Cache only the
// deterministic TypeScript-to-CommonJS output; modules and assertions still
// execute afresh against the current cumulative source tree on every run.
const CACHE_ROOT = process.env.SEGPIPE_TS_CACHE || fs.mkdtempSync(path.join(os.tmpdir(), "apphosting-ts-"));
fs.mkdirSync(CACHE_ROOT, { recursive: true });
if (!process.env.SEGPIPE_TS_CACHE) {
  process.on("exit", () => fs.rmSync(CACHE_ROOT, { recursive: true, force: true }));
}

function register(extension, jsx) {
  require.extensions[extension] = function compile(module, filename) {
    const source = fs.readFileSync(filename, "utf8");
    const cacheKey = crypto
      .createHash("sha256")
      .update(ts.version)
      .update("\0firebase-tools-cjs-es2017-v1\0")
      .update(extension)
      .update("\0")
      .update(source)
      .digest("hex");
    const cachePath = path.join(CACHE_ROOT, `${cacheKey}.js`);
    let outputText;
    try {
      outputText = fs.readFileSync(cachePath, "utf8");
    } catch (error) {
      if (!error || error.code !== "ENOENT") throw error;
      outputText = ts.transpileModule(source, {
        compilerOptions: {
          allowSyntheticDefaultImports: true,
          esModuleInterop: false,
          experimentalDecorators: true,
          jsx,
          module: ts.ModuleKind.CommonJS,
          moduleResolution: ts.ModuleResolutionKind.NodeJs,
          removeComments: true,
          sourceMap: false,
          target: ts.ScriptTarget.ES2017,
        },
        fileName: filename,
        reportDiagnostics: false,
      }).outputText;
      const temporaryPath = `${cachePath}.${process.pid}.tmp`;
      fs.writeFileSync(temporaryPath, outputText, "utf8");
      try {
        fs.renameSync(temporaryPath, cachePath);
      } catch (renameError) {
        try {
          fs.unlinkSync(temporaryPath);
        } catch (_) {}
        if (!fs.existsSync(cachePath)) throw renameError;
      }
    }
    module._compile(outputText, filename);
  };
}

register(".ts", ts.JsxEmit.None);
register(".tsx", ts.JsxEmit.React);
