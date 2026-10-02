# PenguinHarness agent for Harbor

`penguin_agent:PenguinAgent` is a Harbor [installed agent](https://harborframework.com/docs) that runs the PenguinHarness CLI inside each task container. It measures PenguinHarness as shipped: the stock `default_agent` of the installed release, driven headless by `penguin run`.

```bash
export PYTHONPATH="$PWD/agents"          # from the repository root
uvx --from harbor==0.23.0 harbor run -p benchmarks/terminal-bench/tasks -i music-harmony \
  -a penguin_agent:PenguinAgent -m deepseek/deepseek-flash --ak thinking=max -y
```

## What one trial does

1. **Install** (Harbor's setup phase, task network policy of the environment): installs `curl`, `xz`, `tar` and CA certificates with the image's package manager if missing; Node.js (`node_version`, checksum-verified from `node_dist_url`) and `@prismshadow/penguin-cli@<penguin_version>` from npm into `/opt/penguin-bench`. Nothing is added to the image's PATH, so the agent's shell commands keep the task's own toolchain. npm runs with `--ignore-scripts`: the one install script in the tree builds `node-pty`, which only the Web App's terminal loads. About two minutes per trial.
2. **Model entry**: reads the model named by `-m <provider>/<model_id>` from this machine's PenguinHarness configuration, `<data root>/<Project>/.project_config.toml`, where the data root is `host_penguin_home`, else `$PENGUIN_HOME`, else `~/.penguin/data`, and the Project is `host_project_id`, else `$PENGUIN_PROJECT_ID`, else `default_project`. That one `[[models]]` entry (credential, endpoint, client type, pricing) and a `default_model` pointing at it become the container's `/opt/penguin-bench/home/<project_id>/.project_config.toml` (mode 0600), copied with `docker compose cp` from a private temporary file. Every other part of the configuration starts from the product defaults, as in a fresh install. The data root is outside `/logs`, so the credential never reaches the trial directory. The step fails before any install work if the model is missing or has no stored key.
3. **Run** (agent phase): `run.sh` starts a PenguinHarness server on that data root and runs
   ```
   penguin run -m "<instruction>" --workspace <task working directory> \
     --project-id default_project --agent-id default_agent \
     --provider <provider> --model-id <model_id> --thinking <thinking> \
     --approve allow-all --source benchmark --timeout <run_timeout> --json
   ```
   With `max_turns` set, the Agent's turn cap is applied through the local API first (the run is skipped if that fails). If `--timeout` expires, the Task is aborted through the local API and the script waits (up to `abort_wait_sec`) for the session to go idle. It then reads `penguin cost --by session --json` and `--by model`, stops the server, copies every agent's Traces to `/logs/agent/penguin/traces/`, and scrubs the configured key from everything under `/logs/agent`. `populate_context_post_run` repeats that scrub on the host.
4. **Verify**: Harbor runs the task's verifier as usual. A non-zero `penguin run` exit is reported to Harbor as an agent error after the cleanup; the verifier still runs.

## Options (`--ak key=value`)

| Option | Default | Meaning |
| --- | --- | --- |
| `thinking` | `max` | `penguin run --thinking`: `low`, `medium`, `high`, `xhigh` or `max` |
| `penguin_version` | `0.2.13` | npm version of `@prismshadow/penguin-cli`; Harbor's `version` is an alias |
| `run_timeout` | `25m` | soft cap of the Task (`30s`, `25m`, `2h` or bare seconds); keep Harbor's agent timeout at least 300 s longer |
| `abort_wait_sec` | `90` | how long an aborted Task may take to wind down |
| `max_turns` | none (stock: unlimited) | turn cap: LLM requests per Task. `penguin run` has no turn flag; the adapter sets the Agent's `max_turns` (`system_config.yaml`) through the Agent config API before the run, leaving the rest of the stock config as is. A capped Task ends with `[reached max turns (N); stopping]` |
| `host_penguin_home` | `$PENGUIN_HOME`, else `~/.penguin/data` | data root whose model entry is copied |
| `host_project_id` | `$PENGUIN_PROJECT_ID`, else `default_project` | host Project whose model table is read (inside a PenguinHarness session the server sets `PENGUIN_PROJECT_ID`, so a `harbor run` started by an Agent reads its own Project) |
| `project_id`, `agent_id` | `default_project`, `default_agent` | ids inside the container |
| `agent_state_tar` | none | host `.tar.gz` holding an Agent State (the contents of `agents/<agent_id>/agent_state`) to run instead of the stock agent; its `.vault.toml` is dropped |
| `node_version` | `24.18.0` | Node.js for the CLI (the runtime the v0.2.13 installer bundles) |
| `node_dist_url` | `https://nodejs.org/dist` | Node.js release mirror |
| `npm_registry` | npm's default | npm registry URL |

## What lands in the trial directory (`agent/`)

| File | Content |
| --- | --- |
| `penguin-install.json` | package, versions and paths installed |
| `penguin-model-list.txt` | `penguin config model list` inside the container; the key column reads `<configured>` |
| `penguin-run.json` | `penguin run --json`: `{sessionId, status, text}` |
| `penguin-run.stderr` | the CLI's stderr |
| `penguin-cost-by-session.json`, `penguin-cost-by-model.json` | `penguin cost --json` (usage per session and per model) |
| `penguin-outcome.json` | exit code, status, session id, soft-timeout flag, start and end times |
| `penguin-agent-state.txt` | with `agent_state_tar`: the files installed as the Agent State (names only) |
| `penguin/` | server log, stop and abort replies, redaction counts, `traces/<agent>/` |

`AgentContext` is filled from those files: `n_input_tokens` = cache read + cache write (Harbor counts cached input as input), `n_cache_tokens` = cache read, `n_output_tokens` = output, `cost_usd` = the product's own price for the usage (catalog list price with its off-peak schedule, per request time; `null` when part of the usage is unpriced), `model_usage` per model, and `metadata` with the session id, final status (`completed`, `aborted`, `timeout`, `server_failed`, `config_failed`), whether the turn cap was reached, wall seconds of `penguin run`, request and session counts and the versions. A request cut off by an abort is not in the product's usage table, although the provider may bill it.

## Network

The setup phase needs `nodejs.org` (or `node_dist_url`), the npm registry and the image's package mirror; the agent phase needs the model provider's API host. For tasks whose agent phase is not public (DeepSWE), allow that host with `--allow-agent-host api.deepseek.com` or `extra_allowed_hosts` in the job config; Harbor enforces the allowlist with its egress sidecar.

## Limits

- glibc images only (official Node.js builds do not run on musl/Alpine); x86-64 and arm64.
- The credential is readable inside the container while the agent runs, as with any in-container agent. Do not use a key you could not revoke.
