/* Definición de escenarios, puertas, adversarios y progreso/dificultad.
   Coordenadas en unidades de tile (T=32). */

// Estado global de partida (progreso y dificultad creciente).
const GameState = {
  defeated: {},        // "room:idx" -> true
  kills: 0,
  start: null,         // timestamp de inicio (para no reaparecer nada raro)

  isDefeated(room, idx) { return !!this.defeated[room + ':' + idx]; },
  markDefeated(room, idx) {
    if (!this.defeated[room + ':' + idx]) { this.defeated[room + ':' + idx] = true; this.kills++; }
  },
  // La dificultad sube cada 2 derrotas.
  tier() { return Math.floor(this.kills / 2); },

  // Coleccionables (caramelos/estrellas/regalos) para motivar la exploración.
  items: {},
  candies: 0,
  isCollected(room, idx) { return !!this.items[room + ':' + idx]; },
  collect(room, idx) {
    if (!this.items[room + ':' + idx]) { this.items[room + ':' + idx] = true; this.candies++; }
  },

  // Oleada GLOBAL: solo al recoger TODOS los coleccionables de TODAS las salas
  // el juego sube de dificultad (más malos y más rápidos en todas las salas) y
  // se reinician todos los caramelos y adversarios.
  globalWave: 0,
  wave() { return this.globalWave; },
  totalCollectibles() {
    let t = 0;
    for (const k in ROOMS) t += (ROOMS[k].collectibles || []).length;
    return t;
  },
  collectedCount() { return Object.keys(this.items).length; },
  allCollected() { return this.totalCollectibles() > 0 && this.collectedCount() >= this.totalCollectibles(); },
  nextGlobalWave() {
    this.globalWave++;
    this.items = {};      // todos los caramelos reaparecen (en todas las salas)
    this.defeated = {};   // todos los adversarios reaparecen (en todas las salas)
    return this.globalWave;
  },
};

const DIFF_ORDER = ['easy', 'medium', 'hard'];
// Escala la dificultad base del adversario según el progreso del jugador.
function escalateDifficulty(base, tier) {
  let i = DIFF_ORDER.indexOf(base);
  if (i < 0) i = 1;
  i = Math.min(DIFF_ORDER.length - 1, i + Math.floor(tier / 2));
  return DIFF_ORDER[i];
}
// Velocidad de persecución (sube con el progreso).
function chaseSpeed(base, tier) { return Math.min(210, base + tier * 16); }

// Rejilla de pupitres para las aulas.
function deskGrid(x0, y0, cols, rows, dx, dy) {
  const out = [];
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++)
      out.push({ t: 'desk', tx: x0 + c * dx, ty: y0 + r * dy });
  return out;
}

const ROOMS = {
  aula: {
    name: 'Aula de Mates', cols: 20, rows: 14, floor: 'floor_wood', wall: 'wall_class',
    furniture: [
      { t: 'blackboard', tx: 9.5, ty: 1.1 },
      { t: 'plant', tx: 1.3, ty: 2 }, { t: 'plant', tx: 18.7, ty: 2 },
      ...deskGrid(4, 5, 4, 3, 4, 3),
    ],
    enemies: [
      { t: 'teacher', tx: 10, ty: 3, difficulty: 'easy', base: 65, name: 'Profesor' },
      { t: 'student', tx: 16, ty: 8, difficulty: 'easy', base: 80, name: 'Repetidor' },
    ],
    npcs: [{ t: 'nerd', tx: 2, ty: 11 }],
    doors: [{ id: 'to_pasillo', tx: 10, ty: 13, to: 'pasillo', toDoor: 'to_aula', label: 'Pasillo ▼' }],
    collectibles: [
      { tx: 2, ty: 4, type: 'candy' }, { tx: 18, ty: 4, type: 'star' },
      { tx: 6, ty: 6, type: 'candy' }, { tx: 14, ty: 6, type: 'gift' },
      { tx: 2, ty: 9, type: 'star' }, { tx: 18, ty: 9, type: 'candy' },
    ],
    spawn: { tx: 10, ty: 11 },
  },

  pasillo: {
    name: 'Pasillo', cols: 24, rows: 8, floor: 'floor_tile', wall: 'wall_class',
    furniture: [
      { t: 'locker', tx: 3, ty: 1.2 }, { t: 'locker', tx: 5, ty: 1.2 }, { t: 'locker', tx: 7, ty: 1.2 },
      { t: 'locker', tx: 17, ty: 1.2 }, { t: 'locker', tx: 19, ty: 1.2 }, { t: 'locker', tx: 21, ty: 1.2 },
      { t: 'plant', tx: 12, ty: 1.4 },
    ],
    enemies: [
      { t: 'bully', tx: 12, ty: 5, difficulty: 'medium', base: 85, name: 'El Abusón' },
      { t: 'teacher', tx: 5, ty: 3, difficulty: 'medium', base: 70, name: 'Profe de guardia' },
      { t: 'student', tx: 19, ty: 5, difficulty: 'medium', base: 80, name: 'Repetidor' },
    ],
    npcs: [],
    doors: [
      { id: 'to_aula', tx: 12, ty: 0, to: 'aula', toDoor: 'to_pasillo', label: 'Aula ▲' },
      { id: 'to_patio', tx: 23, ty: 4, to: 'patio', toDoor: 'to_pasillo', label: 'Patio ▶' },
      { id: 'to_despacho', tx: 0, ty: 4, to: 'despacho', toDoor: 'to_pasillo', label: '◀ Despacho' },
    ],
    collectibles: [
      { tx: 4, ty: 4, type: 'candy' }, { tx: 9, ty: 3, type: 'star' },
      { tx: 15, ty: 6, type: 'gift' }, { tx: 20, ty: 3, type: 'candy' },
      { tx: 12, ty: 6, type: 'star' },
    ],
    spawn: { tx: 12, ty: 4 },
  },

  patio: {
    name: 'Patio', cols: 22, rows: 16, floor: 'floor_grass', wall: 'fence',
    furniture: [
      { t: 'tree', tx: 3, ty: 3 }, { t: 'tree', tx: 18, ty: 3 }, { t: 'tree', tx: 3, ty: 13 },
      { t: 'hoop', tx: 18, ty: 12 }, { t: 'bench', tx: 8, ty: 14 }, { t: 'bench', tx: 13, ty: 14 },
    ],
    enemies: [
      { t: 'bully', tx: 7, ty: 6, difficulty: 'medium', base: 90, name: 'El Abusón' },
      { t: 'student', tx: 15, ty: 8, difficulty: 'medium', base: 80, name: 'Repetidor' },
      { t: 'bully', tx: 11, ty: 12, difficulty: 'medium', base: 85, name: 'Matón' },
      { t: 'teacher', tx: 18, ty: 4, difficulty: 'medium', base: 72, name: 'Profe de guardia' },
    ],
    npcs: [{ t: 'nerd', tx: 11, ty: 3 }],
    doors: [{ id: 'to_pasillo', tx: 0, ty: 8, to: 'pasillo', toDoor: 'to_patio', label: '◀ Pasillo' }],
    collectibles: [
      { tx: 6, ty: 10, type: 'candy' }, { tx: 14, ty: 6, type: 'star' },
      { tx: 10, ty: 11, type: 'gift' }, { tx: 18, ty: 8, type: 'candy' },
      { tx: 4, ty: 6, type: 'star' }, { tx: 12, ty: 3, type: 'candy' },
      { tx: 20, ty: 14, type: 'gift' },
    ],
    spawn: { tx: 2, ty: 8 },
  },

  despacho: {
    name: 'Despacho de Dirección', cols: 14, rows: 10, floor: 'floor_wood', wall: 'wall_office',
    furniture: [
      { t: 'blackboard', tx: 7, ty: 1.1 }, { t: 'plant', tx: 1.3, ty: 8 }, { t: 'plant', tx: 12.7, ty: 8 },
      { t: 'desk', tx: 7, ty: 4 },
    ],
    enemies: [
      { t: 'director', tx: 7, ty: 3, difficulty: 'hard', base: 105, boss: true, name: 'Dirección' },
      { t: 'teacher', tx: 3, ty: 5, difficulty: 'hard', base: 80, name: 'Jefe de estudios' },
      { t: 'teacher', tx: 11, ty: 5, difficulty: 'hard', base: 80, name: 'Secretaría' },
    ],
    npcs: [],
    doors: [{ id: 'to_pasillo', tx: 13, ty: 5, to: 'pasillo', toDoor: 'to_despacho', label: 'Pasillo ▶' }],
    collectibles: [
      { tx: 3, ty: 6, type: 'star' }, { tx: 10, ty: 7, type: 'candy' }, { tx: 6, ty: 8, type: 'gift' },
    ],
    spawn: { tx: 11, ty: 5 },
  },
};

// Metadatos de tamaño/colisión del mobiliario (ancho, alto de textura).
const FURN_META = {
  blackboard: { w: 176, h: 44, solid: true, body: [176, 22] },
  desk: { w: 36, h: 30, solid: true, body: [34, 22] },
  locker: { w: 26, h: 54, solid: true, body: [26, 50] },
  tree: { w: 54, h: 62, solid: true, body: [16, 16, 0, 20] },
  bench: { w: 52, h: 22, solid: true, body: [52, 16] },
  hoop: { w: 30, h: 70, solid: true, body: [10, 12, 0, 26] },
  plant: { w: 24, h: 30, solid: true, body: [18, 14] },
};
