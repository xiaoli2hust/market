import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

function walk(dir, result = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (['node_modules', 'dist', '.umi', '.umi-production'].includes(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, result);
    else result.push(full);
  }
  return result;
}

const auth = read('src/services/auth.ts');
assert.match(auth, /credentials: 'same-origin'/, 'browser requests must keep same-origin cookies');
assert.doesNotMatch(auth, /market_token/, 'frontend must not persist readable JWT tokens');
assert.match(auth, /userHasPermission/, 'permission checks must use one shared helper');
assert.match(auth, /PERMISSION_LABELS/, 'permission codes need business-facing labels');

const dashboardShared = read('src/pages/Dashboard/dashboardShared.tsx');
assert.match(dashboardShared, /querySelectorAll\('script, iframe, object, embed'\)/, 'HTML preview sanitizer must remove active embeds');
assert.match(dashboardShared, /value\.startsWith\('javascript:'\)/, 'HTML preview sanitizer must block javascript URLs');

const dashboardOverlays = read('src/pages/Dashboard/DashboardOverlays.tsx');
assert.match(dashboardOverlays, /sandbox=""/, 'report previews must render in sandboxed iframes');
assert.match(dashboardOverlays, /sanitizeHtmlForPreview/, 'preview iframes must use sanitized srcDoc');

const botCenter = read('src/pages/BotCenter/index.tsx');
assert.match(botCenter, /renderChatTab/, 'robot center must keep the chat test entry');
assert.match(botCenter, /renderBroadcastTab/, 'robot center must keep controlled broadcast entry');

const tsFiles = walk(path.join(root, 'src')).filter((item) => /\\.(ts|tsx)$/.test(item));
const oversized = tsFiles
  .map((file) => ({ file, lines: read(path.relative(root, file)).split('\\n').length }))
  .filter((item) => item.lines > 600);
assert.deepEqual(oversized, [], 'frontend TypeScript files must stay at or below 600 lines');

console.log('frontend contract tests passed');
