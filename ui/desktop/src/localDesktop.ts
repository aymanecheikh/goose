import { app } from 'electron';
import fs from 'node:fs';
import path from 'node:path';
import * as yaml from 'yaml';
import { DEFAULT_LOCAL_MODEL, LOCAL_CHAT_MODELS, LOCAL_CONTEXT_LIMIT } from './localModels';

const home = app.getPath('home');
const userData = path.join(app.getPath('appData'), 'Goose Local');
const root = process.env.GOOSE_PATH_ROOT || path.join(home, '.local', 'share', 'goose-local');
const workspace = path.join(home, 'AIWorkspace');

app.setName('Goose Local');
fs.mkdirSync(userData, { recursive: true });
app.setPath('userData', userData);
process.env.GOOSE_PATH_ROOT = root;
process.env.GOOSE_DEFAULT_PROVIDER ??= 'ollama';
process.env.GOOSE_DEFAULT_MODEL ??= DEFAULT_LOCAL_MODEL;
process.env.GOOSE_MAX_CONCURRENT_SUBAGENTS ??= '1';

fs.mkdirSync(path.join(root, 'config'), { recursive: true });
fs.mkdirSync(workspace, { recursive: true });

const configFile = path.join(root, 'config', 'config.yaml');
if (!fs.existsSync(configFile)) {
  const tools = path.join(home, '.local', 'share', 'goose-tools', 'node_modules');
  const browserArgs = [path.join(tools, '@playwright/mcp/cli.js')];
  const browserCache = path.join(home, 'Library', 'Caches', 'ms-playwright');
  if (fs.existsSync(browserCache)) {
    const versions = fs.readdirSync(browserCache).filter((name) => /^chromium-\d+$/.test(name));
    versions.sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]));
    for (const version of versions) {
      const executable = path.join(
        browserCache,
        version,
        `chrome-mac-${process.arch}`,
        'Google Chrome for Testing.app',
        'Contents',
        'MacOS',
        'Google Chrome for Testing'
      );
      if (fs.existsSync(executable)) {
        browserArgs.push('--executable-path', executable);
        break;
      }
    }
  }
  browserArgs.push('--headless', '--isolated', '--idle-timeout', '120000');
  const config = `active_provider: ollama
providers:
  ollama:
    enabled: true
    configured: true
    model: ${JSON.stringify(DEFAULT_LOCAL_MODEL)}
OLLAMA_HOST: "http://127.0.0.1:11434"
GOOSE_INPUT_LIMIT: ${LOCAL_CONTEXT_LIMIT}
GOOSE_CONTEXT_LIMIT: ${LOCAL_CONTEXT_LIMIT}
GOOSE_MAX_TOKENS: 4096
GOOSE_THINKING_EFFORT: "off"
GOOSE_TEMPERATURE: 0.2
GOOSE_TELEMETRY_ENABLED: false
extensions:
  developer:
    type: platform
    name: developer
    enabled: true
    bundled: true
  skills:
    type: platform
    name: skills
    enabled: true
    bundled: true
  extensionmanager:
    type: platform
    name: extensionmanager
    enabled: true
    bundled: true
  fetch:
    type: stdio
    name: fetch
    description: Read web pages as text
    enabled: true
    cmd: /opt/homebrew/bin/uvx
    args: ["--with", "mcp<2", "mcp-server-fetch==2025.4.7"]
    timeout: 120
  computercontroller:
    type: builtin
    name: computercontroller
    display_name: Computer Controller
    description: Mac control and PDF, Word, and spreadsheet tools
    enabled: false
    bundled: true
    timeout: 300
  playwright:
    type: stdio
    name: playwright
    description: Browser navigation and automation
    enabled: false
    cmd: /opt/homebrew/bin/node
    args: ${JSON.stringify(browserArgs)}
    timeout: 120
${['analyze', 'apps', 'summon', 'tom', 'scheduler', 'code_execution', 'chatrecall', 'summarize']
  .map(
    (name) =>
      `  ${name}:\n    type: platform\n    name: ${name}\n    enabled: false\n    bundled: true`
  )
  .join('\n')}
`;
  fs.writeFileSync(configFile, config, { mode: 0o600 });
}

const settingsFile = path.join(userData, 'settings.json');
if (!fs.existsSync(settingsFile)) {
  fs.writeFileSync(
    settingsFile,
    JSON.stringify(
      {
        recentModels: LOCAL_CHAT_MODELS.map(({ provider, model }) => ({ provider, model })),
        disableAutoDownload: true,
        showPricing: false,
      },
      null,
      2
    ),
    { mode: 0o600 }
  );
}

const recentDirs = path.join(userData, 'recent-dirs.json');
if (!fs.existsSync(recentDirs)) {
  fs.writeFileSync(recentDirs, JSON.stringify({ dirs: [workspace] }), { mode: 0o600 });
}

const knowledgeConfig = path.join(root, 'config', 'knowledge.json');
if (!fs.existsSync(knowledgeConfig)) {
  fs.writeFileSync(
    knowledgeConfig,
    JSON.stringify(
      {
        roots: [workspace],
        database: path.join(root, 'data', 'knowledge', 'index.sqlite3'),
        model: 'embeddinggemma:latest',
      },
      null,
      2
    ),
    { mode: 0o600 }
  );
}
const profile = yaml.parseDocument(fs.readFileSync(configFile, 'utf8'));
if (!profile.hasIn(['extensions', 'localknowledge'])) {
  const source = path.join(home, '.local/share/goose-tools/knowledge-server');
  profile.setIn(['extensions', 'localknowledge'], {
    type: 'stdio',
    name: 'localknowledge',
    display_name: 'Local Knowledge',
    description: 'Search local notes and documents with EmbeddingGemma',
    enabled: true,
    cmd: path.join(home, '.local/share/goose-tools/knowledge-venv/bin/python'),
    args: [path.join(source, 'server.py'), '--config', knowledgeConfig],
    envs: { PYTHONDONTWRITEBYTECODE: '1' },
    timeout: 600,
  });
  const temporary = `${configFile}.knowledge-tmp`;
  fs.writeFileSync(temporary, profile.toString(), { mode: 0o600 });
  fs.renameSync(temporary, configFile);
}
