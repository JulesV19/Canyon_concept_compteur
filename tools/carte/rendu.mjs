// Fabrique la carte du compteur : des tuiles images pré-rendues à partir des données OpenStreetMap.
// Le compteur n'a pas d'internet et le Pi Zero est trop faible pour dessiner une carte vectorielle :
// on dessine donc tout ici, une fois, avec MapLibre, et le compteur n'a plus qu'à afficher des images.
//
//   node rendu.mjs apercu <lat> <lon> <zoom> <sortie.png>   aperçu de la page carte du compteur
//   node rendu.mjs construire                                carte dans cartes/ile-de-france.mbtiles
//
// Le binaire MapLibre n'existe que jusqu'à Node 24 : npx -p node@24 node rendu.mjs ...

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import mbgl from '@maplibre/maplibre-gl-native';
import sharp from 'sharp';
import { PMTiles } from 'pmtiles';
import { buildStyle } from './style.mjs';

const ROOT = path.resolve(import.meta.dirname, '..', '..');
const SOURCE = path.join(ROOT, 'cartes', 'osm-ile-de-france.pmtiles');
const OUTPUT = path.join(ROOT, 'cartes', 'ile-de-france.mbtiles');
const ROUTES = path.join(ROOT, 'parcours');
const CACHE = path.join(import.meta.dirname, 'cache');
const ASSETS = 'https://protomaps.github.io/basemaps-assets';

// Tuiles standard de 256 px dessinées en x2 : 512 px, affichées pixel pour pixel sur l'écran
// du compteur (285 ppp), ce qui donne des noms de rues lisibles à un bras de distance.
const RATIO = 2;
const TILE = 256;

// Toute la région jusqu'au zoom 12, zooms 13 à 16 autour des parcours (quelques minutes).
// Pour rouler n'importe où sans parcours : REGION_ZOOMS = [8, 16] (bien plus long).
const REGION_ZOOMS = [8, 12];
const ROUTE_ZOOMS = [13, 16];
const ROUTE_BUFFER_M = 3000;

const STYLE = buildStyle('local://tiles/{z}/{x}/{y}.pbf');

// --- Ressources demandées par MapLibre -------------------------------------------------------

class LocalSource {
  constructor(file) {
    this.file = file;
    this.fd = fs.openSync(file, 'r');
  }
  getKey() {
    return this.file;
  }
  async getBytes(offset, length) {
    const buffer = Buffer.alloc(length);
    const read = fs.readSync(this.fd, buffer, 0, length, offset);
    return { data: buffer.buffer.slice(0, read) };
  }
}

const archive = new PMTiles(new LocalSource(SOURCE));

// Polices et icônes Protomaps, téléchargées une fois puis gardées en cache
async function cached(name) {
  const file = path.join(CACHE, name);
  if (!fs.existsSync(file)) {
    const response = await fetch(`${ASSETS}/${name.split('/').map(encodeURIComponent).join('/')}`);
    if (!response.ok) return null;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, Buffer.from(await response.arrayBuffer()));
  }
  return fs.readFileSync(file);
}

async function load(url) {
  const [kind, ...rest] = url.replace('local://', '').split('/');
  if (kind === 'tiles') {
    const [z, x, y] = rest.map((value) => parseInt(value, 10));
    const tile = await archive.getZxy(z, x, y);
    return tile ? Buffer.from(tile.data) : null;
  }
  if (kind === 'fonts') {
    const font = decodeURIComponent(rest[0]).split(',')[0];
    return cached(`fonts/${font}/${rest[1]}`);
  }
  if (kind === 'sprites') return cached(`sprites/v4/${rest[0]}`);
  throw new Error(`ressource inconnue : ${url}`);
}

function request(req, callback) {
  load(req.url)
    .then((data) => (data ? callback(null, { data }) : callback()))
    .catch((error) => callback(error));
}

function createMap(mode) {
  const map = new mbgl.Map({ request, ratio: RATIO, mode });
  map.load(STYLE);
  return map;
}

function render(map, options) {
  return new Promise((resolve, reject) => {
    map.render(options, (error, pixels) => (error ? reject(error) : resolve(pixels)));
  });
}

// --- Géométrie des tuiles ------------------------------------------------------------------

function tileCenter(z, x, y) {
  const n = 2 ** z;
  const lon = ((x + 0.5) / n) * 360 - 180;
  const lat = (Math.atan(Math.sinh(Math.PI * (1 - (2 * (y + 0.5)) / n))) * 180) / Math.PI;
  return [lon, lat];
}

function* tilesIn(z, [minLon, minLat, maxLon, maxLat]) {
  const n = 2 ** z;
  const column = (lon) => Math.floor(((lon + 180) / 360) * n);
  const row = (lat) => Math.floor(((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2) * n);
  for (let x = column(minLon); x <= column(maxLon); x++) {
    for (let y = row(maxLat); y <= row(minLat); y++) yield [z, x, y];
  }
}

// Emprise de chaque parcours GPX, élargie pour pouvoir s'en écarter un peu
function routeBounds() {
  if (!fs.existsSync(ROUTES)) return [];
  return fs.readdirSync(ROUTES).filter((name) => name.endsWith('.gpx')).map((name) => {
    const gpx = fs.readFileSync(path.join(ROUTES, name), 'utf8');
    const points = [...gpx.matchAll(/<(?:trkpt|rtept)\b[^>]*>/g)].map(([tag]) => [
      parseFloat(tag.match(/lon="([^"]+)"/)[1]),
      parseFloat(tag.match(/lat="([^"]+)"/)[1]),
    ]);
    const lons = points.map((p) => p[0]);
    const lats = points.map((p) => p[1]);
    const dLat = ROUTE_BUFFER_M / 111320;
    const dLon = dLat / Math.cos((Math.max(...lats) * Math.PI) / 180);
    return [Math.min(...lons) - dLon, Math.min(...lats) - dLat, Math.max(...lons) + dLon, Math.max(...lats) + dLat];
  });
}

// --- Commandes -------------------------------------------------------------------------------

async function preview(lat, lon, zoom, file) {
  // Même rendu que sur le compteur : zone carte de 480 x 400 pixels
  const width = 480;
  const height = 400;
  const map = createMap('static');
  const pixels = await render(map, {
    zoom: zoom - 1,
    center: [lon, lat],
    width: width / RATIO,
    height: height / RATIO,
  });
  map.release();
  await sharp(pixels, { raw: { width, height, channels: 4 } }).removeAlpha().png().toFile(file);
  console.log(`Aperçu enregistré : ${file}`);
}

async function build() {
  const header = await archive.getHeader();
  const region = [header.minLon, header.minLat, header.maxLon, header.maxLat];

  const jobs = new Map();
  const add = (tile) => jobs.set(tile.join('/'), tile);
  for (let z = REGION_ZOOMS[0]; z <= REGION_ZOOMS[1]; z++) for (const tile of tilesIn(z, region)) add(tile);
  for (const bounds of routeBounds()) {
    for (let z = ROUTE_ZOOMS[0]; z <= ROUTE_ZOOMS[1]; z++) for (const tile of tilesIn(z, bounds)) add(tile);
  }
  const queue = [...jobs.values()];
  console.log(`${queue.length} tuiles à dessiner`);

  const temporary = `${OUTPUT}.tmp`;
  fs.rmSync(temporary, { force: true });
  const db = new DatabaseSync(temporary);
  db.exec(`
    CREATE TABLE metadata (name TEXT, value TEXT);
    CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);
    CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row);
  `);
  const meta = db.prepare('INSERT INTO metadata VALUES (?, ?)');
  for (const [name, value] of Object.entries({
    name: 'Île-de-France',
    format: 'png',
    type: 'baselayer',
    bounds: region.join(','),
    minzoom: String(REGION_ZOOMS[0]),
    maxzoom: String(ROUTE_ZOOMS[1]),
    tilesize: String(TILE * RATIO),
    attribution: '© OpenStreetMap',
  })) meta.run(name, value);
  const insert = db.prepare('INSERT INTO tiles VALUES (?, ?, ?, ?)');

  const started = Date.now();
  let next = 0;
  let done = 0;
  db.exec('BEGIN');
  const worker = async () => {
    const map = createMap('tile');
    while (next < queue.length) {
      const [z, x, y] = queue[next++];
      const pixels = await render(map, { zoom: z - 1, center: tileCenter(z, x, y), width: TILE, height: TILE });
      const size = TILE * RATIO;
      const png = await sharp(pixels, { raw: { width: size, height: size, channels: 4 } })
        .removeAlpha()
        .png({ palette: true, quality: 95, effort: 7 })
        .toBuffer();
      insert.run(z, x, 2 ** z - 1 - y, png);
      if (++done % 500 === 0) {
        db.exec('COMMIT; BEGIN');
        const rate = done / ((Date.now() - started) / 1000);
        console.log(`${done}/${queue.length} tuiles, reste ${Math.round((queue.length - done) / rate)} s`);
      }
    }
    map.release();
  };
  await Promise.all(Array.from({ length: Math.min(4, os.availableParallelism()) }, worker));
  db.exec('COMMIT');
  db.close();
  fs.renameSync(temporary, OUTPUT);
  const megabytes = fs.statSync(OUTPUT).size / 1e6;
  console.log(`Carte enregistrée : ${OUTPUT} (${megabytes.toFixed(0)} Mo, ${Math.round((Date.now() - started) / 1000)} s)`);
}

const [command, ...args] = process.argv.slice(2);
if (command === 'apercu' && args.length === 4) {
  await preview(parseFloat(args[0]), parseFloat(args[1]), parseFloat(args[2]), args[3]);
} else if (command === 'construire') {
  await build();
} else {
  console.log('Usage : node rendu.mjs apercu <lat> <lon> <zoom> <sortie.png> | construire');
  process.exitCode = 1;
}
