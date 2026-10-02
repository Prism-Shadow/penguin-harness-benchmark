// In-container helper for run.sh; runs on the private Node runtime, no dependencies.
//
//   node helper.mjs now
//       Prints the current time in epoch milliseconds.
//   node helper.mjs run-status <penguin-run.json>
//       Prints "<status> <sessionId>" from `penguin run --json` output, or "error -".
//   node helper.mjs abort <data root> <sessionId> <wait seconds>
//       Aborts the session's running Task through the local server and waits until the
//       session is idle. Prints one JSON line.
//   node helper.mjs set-max-turns <data root> <projectId> <agentId> <n>
//       Sets the Agent's max_turns through the local server and reads it back. Prints one
//       JSON line; exits 1 when the value read back differs.
//   node helper.mjs redact <.project_config.toml> <dir>
//       Replaces every api_key value found in the config with "[REDACTED]" in all regular
//       files under <dir>. Prints one JSON line with counts; never prints a key.
//   node helper.mjs outcome <file> <json>
//       Writes <json> (validated) to <file>.
import fs from "node:fs";
import path from "node:path";

function out(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function runStatus(file) {
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8").trim().split("\n").pop());
    const status = typeof parsed.status === "string" ? parsed.status : "error";
    const sessionId = typeof parsed.sessionId === "string" ? parsed.sessionId : "-";
    process.stdout.write(`${status} ${sessionId}\n`);
  } catch {
    process.stdout.write("error -\n");
  }
}

// Same addressing as the CLI: localhost (the server reserves 127.0.0.1 for previews) and
// the Bearer token the server writes to <root>/api-token at every boot.
async function api(root, method, apiPath, body) {
  const lock = JSON.parse(fs.readFileSync(path.join(root, "server.lock"), "utf8"));
  const token = fs.readFileSync(path.join(root, "api-token"), "utf8").trim();
  return fetch(`http://localhost:${lock.port}${apiPath}`, {
    method,
    headers: {
      authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "content-type": "application/json" } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
}

// Sets the Agent's max_turns (system_config.yaml) through the Agent config API, which
// changes that one key and keeps the rest of the stock config, then reads it back.
// Exits non-zero unless the value read back is the one requested.
async function setMaxTurns(root, projectId, agentId, value) {
  const result = { requested: Number(value) };
  const configPath = `/api/projects/${encodeURIComponent(projectId)}/agents/${encodeURIComponent(agentId)}/config`;
  try {
    const put = await api(root, "PUT", configPath, { config: { maxTurns: Number(value) } });
    result.put_status = put.status;
    const get = await api(root, "GET", configPath);
    result.get_status = get.status;
    if (get.ok) result.max_turns = (await get.json())?.config?.maxTurns ?? null;
  } catch (err) {
    result.error = err instanceof Error ? err.message : String(err);
  }
  out(result);
  if (result.max_turns !== result.requested) process.exitCode = 1;
}

async function abort(root, sessionId, waitSeconds) {
  const started = Date.now();
  const result = { aborted: false, status: "unknown", waited_ms: 0 };
  try {
    const res = await api(root, "POST", `/api/sessions/${encodeURIComponent(sessionId)}/abort`);
    result.aborted = res.status === 202;
    result.http_status = res.status;
    const deadline = started + Number(waitSeconds) * 1000;
    while (Date.now() < deadline) {
      const info = await api(root, "GET", `/api/sessions/${encodeURIComponent(sessionId)}`);
      if (info.ok) {
        // GET /api/sessions/:id answers { session: SessionInfo }.
        const body = await info.json();
        result.status = body?.session?.status ?? "unknown";
        if (result.status === "idle") break;
      }
      await sleep(1000);
    }
  } catch (err) {
    result.error = err instanceof Error ? err.message : String(err);
  }
  result.waited_ms = Date.now() - started;
  out(result);
}

// The config is written by PenguinAgent with basic strings only (\" \\ \uXXXX escapes), a
// subset of JSON string syntax, so JSON.parse decodes the value exactly.
function apiKeys(configFile) {
  const text = fs.readFileSync(configFile, "utf8");
  const keys = [];
  for (const match of text.matchAll(/^\s*api_key\s*=\s*"((?:[^"\\]|\\.)*)"\s*$/gm)) {
    const value = JSON.parse(`"${match[1]}"`);
    if (value.length >= 8) keys.push(value);
  }
  return keys;
}

function walk(dir, visit) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, visit);
    else if (entry.isFile()) visit(full);
  }
}

function redact(configFile, dir) {
  const result = { keys: 0, files_scanned: 0, files_redacted: 0 };
  let keys;
  try {
    keys = apiKeys(configFile).map((k) => Buffer.from(k, "utf8"));
  } catch (err) {
    result.error = `cannot read config: ${err instanceof Error ? err.message : String(err)}`;
    out(result);
    return;
  }
  result.keys = keys.length;
  const replacement = Buffer.from("[REDACTED]", "utf8");
  walk(dir, (file) => {
    let data;
    try {
      if (fs.statSync(file).size > 256 * 1024 * 1024) return;
      data = fs.readFileSync(file);
    } catch {
      return;
    }
    result.files_scanned += 1;
    let changed = false;
    for (const key of keys) {
      let at = data.indexOf(key);
      if (at === -1) continue;
      const parts = [];
      let from = 0;
      while (at !== -1) {
        parts.push(data.subarray(from, at), replacement);
        from = at + key.length;
        at = data.indexOf(key, from);
      }
      parts.push(data.subarray(from));
      data = Buffer.concat(parts);
      changed = true;
    }
    if (changed) {
      fs.writeFileSync(file, data);
      result.files_redacted += 1;
    }
  });
  out(result);
}

const [command, ...args] = process.argv.slice(2);
switch (command) {
  case "now":
    process.stdout.write(`${Date.now()}\n`);
    break;
  case "run-status":
    runStatus(args[0]);
    break;
  case "abort":
    await abort(args[0], args[1], args[2] ?? "60");
    break;
  case "set-max-turns":
    await setMaxTurns(args[0], args[1], args[2], args[3]);
    break;
  case "redact":
    redact(args[0], args[1]);
    break;
  case "outcome":
    fs.writeFileSync(args[0], `${JSON.stringify(JSON.parse(args[1]), null, 2)}\n`);
    break;
  default:
    process.stderr.write(`helper.mjs: unknown command ${command}\n`);
    process.exitCode = 2;
}
