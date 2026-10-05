import { readFile, writeFile, mkdir, cp } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.resolve(root, '.vercel/output');
const dist = path.resolve(root, 'apps/web/dist');
if (process.env.VITE_HINAA_AUTH_MODE !== 'clerk') throw new Error('Prepare with VITE_HINAA_AUTH_MODE=clerk after building the authenticated frontend.');
const index = await readFile(path.join(dist, 'index.html'), 'utf8');
if (!index.includes('HINAA')) throw new Error('Build the Hina frontend before preparing production assets.');
const config = JSON.parse(await readFile(path.join(root, 'vercel.json'), 'utf8'));
const endpoint = config.rewrites.find((route) => route.source === '/api/:path*')?.destination;
if (!endpoint) throw new Error('The existing backend rewrite is missing.');
const origin = new URL(endpoint).origin;
await mkdir(path.join(output, 'static'), { recursive: true });
// Deploy only the compiled public frontend. Backend code, credentials, logs,
// databases, and private memories cannot enter this upload.
await cp(dist, path.join(output, 'static'), { recursive: true });
await writeFile(path.join(output, 'config.json'), JSON.stringify({
  version: 3,
  routes: [
    { src: '^/api/(.*)$', dest: `${origin}/api/$1`, headers: { 'Cache-Control': 'no-store' } },
    { src: '^/v1/(.*)$', dest: `${origin}/v1/$1`, headers: { 'Cache-Control': 'no-store' } },
    { src: '^/(health(?:/.*)?|healthz|readyz)$', dest: `${origin}/$1`, headers: { 'Cache-Control': 'no-store' } },
    { handle: 'filesystem' },
    { src: '^/(?!api/|v1/|health|assets/|models/|worklets/).*$', dest: '/index.html' },
  ],
}, null, 2));
console.log('Prepared compiled Hina frontend and API routes for the existing Vercel project.');

await writeFile(path.join(output, 'hina-live-build.json'), JSON.stringify({authMode: 'clerk', preparedAt: new Date().toISOString()}));
