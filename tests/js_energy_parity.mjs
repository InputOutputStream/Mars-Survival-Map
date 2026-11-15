// Usage: node js_energy_parity.mjs <file.json> ; compares with Python (traverse.py)
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
const here = path.dirname(fileURLToPath(import.meta.url));
const { findRouteEnergy } = await import(pathToFileURL(path.join(here, '..', 'web', 'route.mjs')).href);
const j = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const r = findRouteEnergy({ dem: Float64Array.from(j.dem), tmult: Float64Array.from(j.tmult, v => v === null ? Infinity : v),
  w: j.w, h: j.h, px: j.px, walker: j.walker, objective: j.objective }, j.start, j.goal);
console.log(JSON.stringify(r ? { n: r.path.length, energy_j: r.energy_j, time_h: r.time_h, length_m: r.length_m } : null));
