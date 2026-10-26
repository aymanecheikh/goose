# Local Knowledge

A stdio MCP extension for Goose using the installed `embeddinggemma:latest`
model through local Ollama. Both Qwen and Gemma use the same SQLite index.
It exposes `knowledge_search`, `knowledge_index`, and `knowledge_status`.

Run `scripts/local-ai/build-desktop.sh` from the repository root to install the
locked Python runtime, install the server into
`~/.local/share/goose-tools/knowledge-server/`, and bundle a source copy. Goose Local creates
`~/.local/share/goose-local/config/knowledge.json` on launch, initially indexing
only `~/AIWorkspace`. Indexing is explicit; there is no background watcher.

The configuration contains `roots` (absolute folder paths), `database` (SQLite
path), and `model` (`embeddinggemma:latest`). After changing roots, refresh the
index. Changed/deleted/out-of-scope documents are excluded from retrieval even
before that refresh. Hidden files, symlinks, and dependency/build folders are
excluded. See [LOCAL_DESKTOP.md](../../LOCAL_DESKTOP.md) for format and size limits.

The runtime streams vectors from SQLite and keeps only the best matches in
memory. A maximum of eight small documents/chunks is sent per embedding call.
Unchanged documents and the last 100 query vectors are reused. EmbeddingGemma
is unloaded in a `finally` block after each embedding operation. Ollama's
one-model limit remains active, so answering may require a chat-model reload.
No vector database daemon, automatic chat storage, or model router is added.

Run deterministic tests from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=extensions/local-knowledge \
  ~/.local/share/goose-tools/knowledge-venv/bin/python -m unittest discover \
  -s extensions/local-knowledge/tests -v
```

The server also supports `--action index`, `--action status`, and
`--action search --query "..."` alongside its required `--config` argument.
The focused Goose recipe phase `test_phases=local-knowledge` checks actual
tool use against the local setup note. Recipes supply their own extension list;
pass the server command with `--with-extension` when using that recipe. Normal
Goose Local chats load Local Knowledge from the profile automatically.

Implementation references: [Ollama embedding API](https://docs.ollama.com/api/embed),
[EmbeddingGemma retrieval prefixes](https://ai.google.dev/gemma/docs/embeddinggemma/model_card).
