// Style « Graphite » du compteur, construit sur le fond Protomaps (données OpenStreetMap).
import { layers, namedFlavor } from '@protomaps/basemaps';

const LAND = '#1c1d20';  // identique à Theme.mapLand (compteur/ui/Theme.qml)
const HALO = '#151618';  // graphite, le fond de l'interface

// Palette graphite, accordée à l'interface : terres gris carbone, eau et forêts à peine teintées,
// routes grises sans liseré, de plus en plus claires avec leur importance. Le parcours, en laque,
// reste le trait le plus clair de la carte.
const flavor = {
  ...namedFlavor('dark'),
  background: '#141a21',
  earth: LAND,
  water: '#161e27',
  park_a: '#1c2620', park_b: '#1e2922',
  wood_a: '#1c2620', wood_b: '#1c2620',
  scrub_a: '#1e2320', scrub_b: '#1e2320',
  hospital: '#241f22', industrial: '#212226', school: '#222127', pedestrian: '#242529',
  beach: '#27251f', sand: '#27251f', zoo: '#1c2621', military: '#242121',
  aerodrome: '#212226', runway: '#323438', glacier: '#24252a', pier: '#2a2b2f',
  buildings: '#2a2b2f',

  other: '#303236', minor_service: '#323438', minor_a: '#43464a', minor_b: '#3c3f43',
  link: '#4f5256', major: '#5a5d62', highway: '#6e7277',
  minor_service_casing: LAND, minor_casing: LAND, link_casing: LAND,
  major_casing_early: LAND, major_casing_late: LAND,
  highway_casing_early: LAND, highway_casing_late: LAND,

  tunnel_other: '#2a2b2f', tunnel_minor: '#2a2b2f', tunnel_link: '#2a2b2f',
  tunnel_major: '#2a2b2f', tunnel_highway: '#2a2b2f',
  tunnel_other_casing: LAND, tunnel_minor_casing: LAND, tunnel_link_casing: LAND,
  tunnel_major_casing: LAND, tunnel_highway_casing: LAND,

  bridges_other: '#303236', bridges_minor: '#43464a', bridges_link: '#4f5256',
  bridges_major: '#5a5d62', bridges_highway: '#6e7277',
  bridges_other_casing: HALO, bridges_minor_casing: HALO, bridges_link_casing: HALO,
  bridges_major_casing: HALO, bridges_highway_casing: HALO,

  railway: '#404246',
  boundaries: '#44464b',

  roads_label_minor: '#8a8d8b', roads_label_minor_halo: LAND,
  roads_label_major: '#a9acaa', roads_label_major_halo: LAND,
  ocean_label: '#56708a',
  subplace_label: '#8f9290', subplace_label_halo: HALO,
  city_label: '#e1e2e0', city_label_halo: HALO,
  state_label: '#55585d', state_label_halo: HALO,
  country_label: '#8a8d8b',
  address_label: '#66696d', address_label_halo: LAND,

  landcover: {
    grassland: '#1e221f',
    barren: '#232325',
    urban_area: '#222326',
    farmland: LAND,
    glacier: '#24252a',
    scrub: '#1e2320',
    forest: '#1c2620',
  },
};

// Trop chargé pour un écran de 2,8" : points d'intérêt, numéros, cartouches, frontières
const HIDDEN = new Set([
  'pois', 'roads_shields', 'roads_oneway', 'address_label',
  'places_country', 'places_region', 'boundaries_country', 'boundaries',
]);

// Pistes cyclables en vert discret, par-dessus les chemins
const CYCLEWAYS = {
  id: 'roads_cycleway',
  type: 'line',
  source: 'protomaps',
  'source-layer': 'roads',
  filter: ['==', ['get', 'kind_detail'], 'cycleway'],
  paint: {
    'line-color': '#2e7d57',
    'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 13, 0.8, 16, 2.4, 18, 6],
  },
};

export function buildStyle(tilesUrl) {
  const base = layers('protomaps', flavor, { lang: 'fr' }).filter((layer) => !HIDDEN.has(layer.id));
  const index = base.findIndex((layer) => layer.id === 'roads_other');
  base.splice(index + 1, 0, CYCLEWAYS);
  return {
    version: 8,
    glyphs: 'local://fonts/{fontstack}/{range}.pbf',
    sprite: 'local://sprites/dark',
    sources: {
      protomaps: {
        type: 'vector',
        tiles: [tilesUrl],
        minzoom: 0,
        maxzoom: 15,
        attribution: '© OpenStreetMap',
      },
    },
    layers: base,
  };
}
