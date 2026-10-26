# Goose Local

This personal fork targets an Apple Silicon Mac running local models through
Ollama. It is based on Goose v1.56.0 and keeps the upstream repository available
as the `upstream` remote.

## What changes

- The app is named **Goose Local**, with a separate macOS bundle identity.
- The model menu always offers **Qwen 9B** and **Gemma 12B** directly.
- Qwen is the default after the checked task comparison below.
- The initial context budget is 16,384 tokens, with thinking off and one
  concurrent subagent. Ollama serializes inference requests.
- File, shell, skills, and web-fetch tools are active initially. Browser,
  document, and Mac-control tools are available to enable when required.
- App updates are maintained through this fork; the official Goose updater is
  disabled for the custom app.

EmbeddingGemma remains installed in Ollama for future semantic-search and
retrieval integration. It is an embedding model and is not a chat-menu choice.
No semantic index or automatic model-quality router is configured yet.

## Build and run

```sh
./scripts/local-ai/build-desktop.sh
```

The script installs the pinned UI dependencies through Hermit, builds the
desktop interface from this fork, and bundles the unmodified official Goose
1.56.0 engine. It uses the installed official app's engine when available,
otherwise downloads the pinned release with SHA-256 verification. It then signs
the local app ad hoc with the upstream entitlements.

The output is `ui/desktop/out/Goose Local-darwin-arm64/Goose Local.app`.
Install that app as `/Applications/Goose Local.app`.

To modify the Rust engine, build it from the fork using the upstream development
instructions, then set `GOOSE_ENGINE_BINARY` to that build before packaging.
Source changes under `ui/desktop` affect this custom interface; editing the clone
does not change an already installed app until it is rebuilt.

The custom app uses:

- `~/.local/share/goose-local/` for backend config, sessions, and state;
- `~/Library/Application Support/Goose Local/` for desktop preferences;
- `~/AIWorkspace/` as its initial working directory.

First-run defaults are seeded only when those files do not exist. User settings
are preserved on subsequent launches. Screen Recording and app-control
permissions belong to this separate app identity and require macOS consent.

## Ollama memory policy

On this Mac, Ollama runs as a user LaunchAgent named
`io.github.aymanecheikh.ollama-local`, replacing the app's login launcher. Its
binary still comes from the official Ollama app. The server listens only on
`127.0.0.1:11434` with:

```text
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_NUM_PARALLEL=1
OLLAMA_KEEP_ALIVE=2m
OLLAMA_CONTEXT_LENGTH=16384
```

These limits persist across login. They conservatively serialize all models,
including embedding requests. Keep the official Ollama app installed, and
update that app manually when needed; restart the LaunchAgent after an update.
The setup can be reproduced with `python3 scripts/local-ai/configure-ollama.py`
while no model work is in progress.

## Model comparison

The checked tasks cover expense analysis, Word document creation, Python code
repair, and source-grounded web research. Each model was run once per task,
using the same input, tools, 16k context budget, 2,048-token output limit,
thinking-off setting, and temperature of 0.2. Model order alternates by task.

| Model | Tasks passed | Total elapsed |
| --- | --- | --- |
| Qwen 3.5 9B Q4_K_M | 4/4 | 235.4 seconds |
| Gemma 4 12B Q4_K_M | 4/4 | 310.9 seconds |

Qwen was faster on all four tasks, about 24% faster overall, and is the default
for this hardware and task mix. Gemma remains a directly selectable alternative.
Timings include cold loading, tool startup, and web latency. Four checked tasks
do not establish universal model quality.

Ollama's API memory figures for Gemma were inconsistent with its much larger
primary weight buffers in the loader logs. They are not used as total-resident
memory measurements. The serial-model policy is verified separately by sending
requests for both models concurrently and observing at most one loaded model.

The reproducible aggregate is in `scripts/local-ai/results/2026-10-26.json`.
To repeat the comparison into a fresh directory:

```sh
python3 scripts/local-ai/benchmark.py --output /tmp/goose-local-comparison
```
