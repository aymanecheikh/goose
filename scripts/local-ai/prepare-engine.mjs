import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const version = '1.56.0';
let source = process.env.GOOSE_ENGINE_BINARY || '/Applications/Goose.app/Contents/Resources/bin/goose';
let temporary;

try {
  if (!fs.existsSync(source)) {
    temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'goose-local-engine-'));
    const url = `https://github.com/aaif-goose/goose/releases/download/v${version}/goose-aarch64-apple-darwin.tar.gz`;
    const response = await fetch(url, { signal: AbortSignal.timeout(180000) });
    if (!response.ok) throw new Error(`Engine download failed: HTTP ${response.status}`);
    const archive = Buffer.from(await response.arrayBuffer());
    const digest = crypto.createHash('sha256').update(archive).digest('hex');
    if (digest !== '52f3f8d62e3d144c5de70c5c471de39d8b92c24d41d5b3436eb8bab11ba4bc24') {
      throw new Error('Released engine checksum did not match');
    }
    const archivePath = path.join(temporary, 'engine.tar.gz');
    fs.writeFileSync(archivePath, archive);
    execFileSync('tar', ['-xzf', archivePath, '-C', temporary]);
    source = path.join(temporary, 'goose');
  }
  const actual = execFileSync(source, ['--version'], { encoding: 'utf8' }).trim();
  if (!actual.startsWith(version)) throw new Error(`Expected engine ${version}, found ${actual}`);
  const directory = path.join(root, 'ui/desktop/src/bin');
  fs.mkdirSync(directory, { recursive: true });
  const destination = path.join(directory, 'goose');
  fs.rmSync(destination, { force: true });
  fs.copyFileSync(source, destination);
  fs.chmodSync(destination, 0o755);
  console.log(`Prepared Goose ${version} engine for the custom desktop build`);
} finally {
  if (temporary) fs.rmSync(temporary, { recursive: true, force: true });
}
