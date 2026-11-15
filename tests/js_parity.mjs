// Compares web/route.mjs (browser) with the Python output on an exported site. Usage: node js_parity.mjs <site_folder>
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
const here = path.dirname(fileURLToPath(import.meta.url));
const { findRoute } = await import(pathToFileURL(path.join(here, '..', 'web', 'route.mjs')).href);
const dir = process.argv[2];
const meta = JSON.parse(readFileSync(`${dir}/site.json`, 'utf8'));
const f32 = f => { const b = readFileSync(`${dir}/${f}`); return new Float32Array(b.buffer, b.byteOffset, b.byteLength / 4); };
const g = { dem: f32('dem.bin'), cost: f32('cost.bin'), w: meta.width, h: meta.height, px: meta.px_m, climbK: meta.params.climb_k, speedKmh: meta.params.speed_kmh };
const out = meta.routes.map(rt => {
  const a = rt.points[0], b = rt.points.at(-1), js = findRoute(g, [a.row, a.col], [b.row, b.col]);
  return { py_len: rt.length_m, js_len: js.length_m, py_time: rt.time_h, js_time: js.time_h, py_n: rt.points.length, js_n: js.path.length };
});
console.log(JSON.stringify(out));
