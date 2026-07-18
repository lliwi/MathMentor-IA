/* Escena de juego por habitaciones (estilo Zelda escolar).
   - Escenarios temáticos (aula, pasillo, patio, despacho) con mobiliario y colisiones.
   - Puertas que transicionan entre pantallas.
   - Adversarios con IA de persecución y dificultad creciente. */
const T = 32;

// RNG con semilla (para posiciones deterministas por sala+oleada).
function hashStr(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
function mulberry32(a) {
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

class RoomScene extends Phaser.Scene {
  constructor() { super('RoomScene'); }

  init(data) {
    this.roomKey = (data && data.room) || 'aula';
    this.entryDoor = (data && data.entry) || null;
    if (!GameState.start) GameState.start = Date.now();
  }

  preload() { Sprites.buildAll(this); }

  create() {
    const room = ROOMS[this.roomKey];
    this.room = room;
    const W = room.cols * T, H = room.rows * T;
    this.physics.world.setBounds(0, 0, W, H);

    // Suelo
    for (let y = 0; y < room.rows; y++)
      for (let x = 0; x < room.cols; x++)
        this.add.image(x * T + T / 2, y * T + T / 2, room.floor).setDepth(0);

    // Muros perimetrales (con hueco en las puertas)
    this.solids = this.physics.add.staticGroup();
    const doorTiles = new Set(room.doors.map((d) => d.tx + ',' + d.ty));
    for (let x = 0; x < room.cols; x++) { this.tryWall(x, 0, room.wall, doorTiles); this.tryWall(x, room.rows - 1, room.wall, doorTiles); }
    for (let y = 0; y < room.rows; y++) { this.tryWall(0, y, room.wall, doorTiles); this.tryWall(room.cols - 1, y, room.wall, doorTiles); }

    // Mobiliario
    room.furniture.forEach((f) => this.addFurniture(f));

    // Puertas
    this.doors = this.physics.add.staticGroup();
    room.doorObjs = [];
    room.doors.forEach((d) => this.addDoor(d));

    // Título del escenario
    this.add.text(W / 2, 6, room.name, {
      fontSize: '13px', color: '#ffffff', backgroundColor: '#000000aa', padding: { x: 8, y: 3 },
    }).setOrigin(0.5, 0).setScrollFactor(1).setDepth(50);

    // Jugador
    const sp = this.spawnPoint();
    this.player = this.physics.add.sprite(sp.x, sp.y, 'player').setDepth(10);
    this.player.body.setSize(16, 14).setOffset(6, 20);
    this.player.setCollideWorldBounds(true);
    this.physics.add.collider(this.player, this.solids);

    // Adversarios (con oleada global: más malos y más rápidos)
    this.wave = GameState.wave();
    this.enemies = this.physics.add.group();
    this.enemyLabels = [];
    room.enemies.forEach((e, idx) => this.addEnemy(e, idx, this.wave));
    // Adversarios extra según la oleada (hasta 6 más)
    const extra = Math.min(this.wave, 6);
    for (let w = 0; w < extra; w++) {
      const tmpl = room.enemies[w % room.enemies.length];
      const rx = Phaser.Math.Between(2, room.cols - 3);
      const ry = Phaser.Math.Between(2, room.rows - 3);
      this.addEnemy(Object.assign({}, tmpl, { tx: rx, ty: ry }), 100 + w, this.wave);
    }
    this.physics.add.collider(this.enemies, this.solids);
    this.physics.add.overlap(this.player, this.enemies, this.onEnemyContact, null, this);

    // NPCs (empollón). La tienda se abre por detección de proximidad en update()
    // (solo al ACERCARSE), no con overlap continuo, para no reabrirse si te quedas encima.
    this.npcs = this.physics.add.staticGroup();
    (room.npcs || []).forEach((n) => this.addNpc(n));

    // Coleccionables (caramelos, estrellas, regalos): posiciones aleatorias por oleada
    this.items = this.physics.add.group();
    const defs = room.collectibles || [];
    if (defs.length) {
      const positions = this.collectiblePositions(room, defs.length);
      defs.forEach((c, i) => {
        const p = positions[i] || { tx: c.tx, ty: c.ty };
        this.addCollectible({ tx: p.tx, ty: p.ty, type: c.type }, i);
      });
    }
    this.physics.add.overlap(this.player, this.items, this.onItemPickup, null, this);

    // Puertas: overlap
    this.physics.add.overlap(this.player, this.doors, this.onDoorContact, null, this);

    // Controles. WASD sin captura (enableCapture=false) para que, al escribir en los
    // formularios de ejercicio/resumen, las letras lleguen al <textarea> en vez de ser
    // interpretadas como movimiento.
    this.cursors = this.input.keyboard.createCursorKeys();
    this.wasd = this.input.keyboard.addKeys('W,A,S,D', false);

    // Cámara
    this.cameras.main.setBounds(0, 0, W, H);
    this.cameras.main.startFollow(this.player, true, 0.12, 0.12);
    this.cameras.main.setZoom(1.6);
    this.cameras.main.fadeIn(250);

    this.frozen = false;
    this._waveStarting = false;
    // Reactiva el teclado por si la escena se reinició estando congelada (p. ej. tras
    // una oleada global), evitando que el jugador quede bloqueado sin poder moverse.
    this.input.keyboard.enabled = true;
    if (this.input.keyboard.enableGlobalCapture) this.input.keyboard.enableGlobalCapture();
    this.doorCooldown = this.time.now + 500;
    // Periodo de gracia al entrar: da tiempo a orientarse antes del primer combate.
    this.contactCooldown = this.time.now + 1300;
    this.npcCooldown = 0;
    this.npcTouching = false;

    if (window.UI) { UI.setRoom(room.name, GameState.tier()); UI.setCandies(GameState.candies); }
  }

  // ---- Construcción ----
  tryWall(cx, cy, tex, doorTiles) {
    if (doorTiles.has(cx + ',' + cy)) return;
    const w = this.solids.create(cx * T + T / 2, cy * T + T / 2, tex).setDepth(2);
    w.refreshBody();
  }

  addFurniture(f) {
    const meta = FURN_META[f.t];
    const px = f.tx * T + T / 2, py = f.ty * T + T / 2;
    const img = this.solids.create(px, py, f.t).setDepth(3);
    if (meta && meta.solid && meta.body) {
      const [bw, bh, ox, oy] = meta.body;
      img.body.setSize(bw, bh);
      // Reposiciona el cuerpo (por defecto centrado); aplica offset opcional hacia los pies.
      img.body.setOffset((meta.w - bw) / 2, (meta.h - bh) / 2 + (oy || 0));
    }
    img.refreshBody();
    // Profundidad por posición para efecto de solapamiento
    img.setDepth(3 + py / 1000);
  }

  addDoor(d) {
    const px = d.tx * T + T / 2, py = d.ty * T + T / 2;
    const door = this.doors.create(px, py, 'door').setDepth(2);
    door.doorData = d;
    door.refreshBody();
    this.add.text(px, py - 22, d.label || 'Puerta', {
      fontSize: '9px', color: '#fff', backgroundColor: '#000000aa', padding: { x: 3, y: 1 },
    }).setOrigin(0.5).setDepth(50);
  }

  addEnemy(e, idx, wave) {
    if (GameState.isDefeated(this.roomKey, idx)) return;
    const tier = GameState.tier();
    wave = wave || 0;
    const en = this.enemies.create(e.tx * T, e.ty * T, e.t).setDepth(10);
    en.body.setSize(16, 14).setOffset(6, 20);
    en.setCollideWorldBounds(true).setBounce(1);
    en.meta = e;
    en.idx = idx;
    en.detect = 150 + tier * 12 + wave * 10;
    en.speed = Math.min(240, chaseSpeed(e.base || 50, tier) + wave * 16);
    en.diff = escalateDifficulty(e.difficulty, tier);
    if (e.boss) en.setScale(1.25);
    en.setVelocity(Phaser.Math.Between(-40, 40), Phaser.Math.Between(-40, 40));
    const t = this.add.text(en.x, en.y - 22, e.name + ' · ' + this.diffIcon(en.diff), {
      fontSize: '9px', color: '#ffdede', backgroundColor: '#00000088', padding: { x: 3, y: 1 },
    }).setOrigin(0.5).setDepth(50);
    this.enemyLabels.push({ e: en, t });
  }

  // Tiles ocupados por muros, mobiliario, puertas, spawn, NPCs y adversarios.
  blockedTiles(room) {
    const b = new Set();
    const add = (x, y) => b.add(x + ',' + y);
    for (let x = 0; x < room.cols; x++) { add(x, 0); add(x, room.rows - 1); }
    for (let y = 0; y < room.rows; y++) { add(0, y); add(room.cols - 1, y); }
    room.doors.forEach((d) => { add(d.tx, d.ty); });
    (room.furniture || []).forEach((f) => {
      const m = FURN_META[f.t];
      const cx = Math.round(f.tx), cy = Math.round(f.ty);
      if (!m) { add(cx, cy); return; }
      const hw = Math.ceil((m.w / T) / 2), hh = Math.ceil((m.h / T) / 2);
      for (let y = cy - hh; y <= cy + hh; y++)
        for (let x = cx - hw; x <= cx + hw; x++) add(x, y);
    });
    add(Math.round(room.spawn.tx), Math.round(room.spawn.ty));
    (room.npcs || []).forEach((n) => add(Math.round(n.tx), Math.round(n.ty)));
    (room.enemies || []).forEach((e) => add(Math.round(e.tx), Math.round(e.ty)));
    return b;
  }

  // Posiciones aleatorias (deterministas por sala+oleada) para los coleccionables.
  collectiblePositions(room, count) {
    const blocked = this.blockedTiles(room);
    const free = [];
    for (let y = 1; y < room.rows - 1; y++)
      for (let x = 1; x < room.cols - 1; x++)
        if (!blocked.has(x + ',' + y)) free.push({ tx: x, ty: y });
    const rng = mulberry32(hashStr(this.roomKey + '#' + this.wave));
    for (let i = free.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      const tmp = free[i]; free[i] = free[j]; free[j] = tmp;
    }
    return free.slice(0, count);
  }

  addCollectible(c, idx) {
    if (GameState.isCollected(this.roomKey, idx)) return;
    const item = this.items.create(c.tx * T + T / 2, c.ty * T + T / 2, c.type || 'candy').setDepth(6);
    item.idx = idx;
    item.body.setAllowGravity(false);
    item.body.setSize(16, 16);
    // Flotación para llamar la atención
    this.tweens.add({ targets: item, y: item.y - 4, duration: 700, yoyo: true, repeat: -1, ease: 'Sine.easeInOut' });
  }

  onItemPickup(player, item) {
    if (item.collected) return;
    item.collected = true;
    GameState.collect(this.roomKey, item.idx);
    UI.setCandies(GameState.candies);
    this.tweens.killTweensOf(item);
    const fx = this.add.text(item.x, item.y - 8, '+1', { fontSize: '11px', color: '#ffcb47', fontStyle: 'bold' })
      .setOrigin(0.5).setDepth(60);
    this.tweens.add({ targets: fx, y: fx.y - 22, alpha: 0, duration: 650, onComplete: () => fx.destroy() });
    this.tweens.add({ targets: item, y: item.y - 12, scale: 1.7, alpha: 0, duration: 260, onComplete: () => item.destroy() });

    // ¿Todos los coleccionables de TODAS las salas recogidos? → nueva oleada global.
    if (GameState.allCollected()) this.startGlobalWave();
  }

  startGlobalWave() {
    if (this._waveStarting) return;
    this._waveStarting = true;
    const n = GameState.nextGlobalWave();
    UI.toast('🎉 ¡Todas las salas completadas! Dificultad ' + (n + 1) + ': más malos y más rápidos.');
    this.freeze(true);
    this.cameras.main.fadeOut(300);
    this.time.delayedCall(320, () => this.scene.restart({ room: this.roomKey, entry: null }));
  }

  addNpc(n) {
    const npc = this.npcs.create(n.tx * T, n.ty * T, n.t).setDepth(10);
    npc.body.setSize(18, 16).setOffset(5, 18);
    npc.refreshBody();
    this.add.text(npc.x, npc.y - 20, '🤓', { fontSize: '14px' }).setOrigin(0.5).setDepth(50);
  }

  diffIcon(d) { return d === 'easy' ? '🟢' : d === 'hard' ? '🔴' : '🟡'; }

  spawnPoint() {
    const room = this.room;
    let tile = room.spawn;
    if (this.entryDoor) {
      const d = room.doors.find((x) => x.id === this.entryDoor);
      if (d) {
        // Aparece 1.5 tiles hacia el interior desde la puerta.
        let tx = d.tx, ty = d.ty;
        if (d.ty === 0) ty = 1.5; else if (d.ty === room.rows - 1) ty = room.rows - 2.5;
        if (d.tx === 0) tx = 1.5; else if (d.tx === room.cols - 1) tx = room.cols - 2.5;
        tile = { tx, ty };
      }
    }
    return { x: tile.tx * T + T / 2, y: tile.ty * T + T / 2 };
  }

  // ---- Interacciones ----
  onDoorContact(player, door) {
    if (UI.isBusy() || this.frozen || this.time.now < this.doorCooldown) return;
    const d = door.doorData;
    this.doorCooldown = this.time.now + 800;
    this.cameras.main.fadeOut(200);
    this.time.delayedCall(210, () => this.scene.restart({ room: d.to, entry: d.toDoor }));
  }

  openNerdShop() {
    this.freeze(true);
    UI.openShop();
    const check = this.time.addEvent({
      delay: 200, loop: true, callback: () => {
        if (document.getElementById('shop-overlay').classList.contains('hidden')) {
          this.freeze(false);
          // Desactiva al empollón unos segundos tras cerrar, para poder alejarte.
          this.npcCooldown = this.time.now + 3000;
          check.remove();
        }
      },
    });
  }

  onEnemyContact(player, enemy) {
    if (UI.isBusy() || this.time.now < this.contactCooldown) return;
    this.freeze(true);
    enemy.setVelocity(0, 0);
    UI.startBattle({ title: enemy.meta.name, difficulty: enemy.diff }, (defeated) => {
      this.freeze(false);
      this.contactCooldown = this.time.now + 1200;
      if (defeated) {
        // Resultado correcto → el adversario desaparece.
        GameState.markDefeated(this.roomKey, enemy.idx);
        const lbl = this.enemyLabels.find((l) => l.e === enemy);
        if (lbl && lbl.t) lbl.t.destroy();
        this.tweens.add({ targets: enemy, alpha: 0, scale: 0, duration: 300, onComplete: () => enemy.destroy() });
        UI.setRoom(this.room.name, GameState.tier());
        if (enemy.meta.boss) UI.toast('🏆 ¡Has vencido a Dirección! Curso superado.');
      } else {
        // Resultado incorrecto → el adversario solo cambia de posición.
        this.repositionEnemy(enemy, player);
        UI.toast('El adversario se ha reubicado. ¡Inténtalo de nuevo!');
      }
    });
  }

  // Reubica al adversario lo más lejos posible del jugador (tras un fallo).
  repositionEnemy(enemy, player) {
    const room = this.room;
    let best = { x: enemy.x, y: enemy.y }, bestD = -1;
    for (let i = 0; i < 14; i++) {
      const px = Phaser.Math.Between(2, room.cols - 3) * T + T / 2;
      const py = Phaser.Math.Between(2, room.rows - 3) * T + T / 2;
      const d = Phaser.Math.Distance.Between(px, py, player.x, player.y);
      if (d > bestD) { bestD = d; best = { x: px, y: py }; }
    }
    enemy.setPosition(best.x, best.y);
    enemy.setVelocity(Phaser.Math.Between(-45, 45), Phaser.Math.Between(-45, 45));
  }

  freeze(on) {
    this.frozen = on;
    // Cede el teclado al DOM mientras hay un overlay abierto (escribir respuestas).
    const kb = this.input.keyboard;
    if (on) {
      this.player.setVelocity(0, 0);
      this.enemies.getChildren().forEach((e) => e.active && e.setVelocity(0, 0));
      window.LegendInput.up = window.LegendInput.down = window.LegendInput.left = window.LegendInput.right = false;
      if (window.LegendUI && window.LegendUI.clearDpad) window.LegendUI.clearDpad();
      kb.enabled = false;
      if (kb.disableGlobalCapture) kb.disableGlobalCapture();
    } else {
      kb.enabled = true;
      if (kb.enableGlobalCapture) kb.enableGlobalCapture();
      // Limpia estados de tecla "pegados": si soltaste una tecla mientras el teclado
      // estaba desactivado (modal abierto), Phaser se perdió el keyup y creería que
      // sigue pulsada, empujando al jugador (p. ej. contra la pared al salir del empollón).
      if (kb.resetKeys) kb.resetKeys();
    }
  }

  update() {
    // Etiquetas siguen a los adversarios
    this.enemyLabels.forEach((l) => { if (l.e.active && l.t) l.t.setPosition(l.e.x, l.e.y - 22); });

    if (this.frozen) { this.player.setVelocity(0, 0); return; }

    // Movimiento del jugador (teclado + D-pad táctil en window.LegendInput)
    const speed = 180;
    const t = window.LegendInput || {};
    let vx = 0, vy = 0;
    if (this.cursors.left.isDown || this.wasd.A.isDown || t.left) vx = -speed;
    else if (this.cursors.right.isDown || this.wasd.D.isDown || t.right) vx = speed;
    if (this.cursors.up.isDown || this.wasd.W.isDown || t.up) vy = -speed;
    else if (this.cursors.down.isDown || this.wasd.S.isDown || t.down) vy = speed;
    this.player.setVelocity(vx, vy);
    if (vx < 0) this.player.setFlipX(true); else if (vx > 0) this.player.setFlipX(false);

    // Empollón: abre la tienda SOLO al acercarse (flanco de entrada) y si no está en
    // cooldown. Si te quedas encima tras cerrar, no se reabre (npcTouching sigue true);
    // debes salir de su radio y volver a entrar.
    if (this.npcs) {
      let touching = false;
      this.npcs.getChildren().forEach((n) => {
        if (Phaser.Math.Distance.Between(n.x, n.y, this.player.x, this.player.y) < 26) touching = true;
      });
      if (touching && !this.npcTouching && !UI.isBusy() && this.time.now >= this.npcCooldown) {
        this.openNerdShop();
      }
      this.npcTouching = touching;
    }

    // IA de adversarios: persiguen si el jugador está cerca; si no, deambulan.
    this.enemies.getChildren().forEach((e) => {
      if (!e.active) return;
      const d = Phaser.Math.Distance.Between(e.x, e.y, this.player.x, this.player.y);
      if (d < e.detect) {
        const ang = Phaser.Math.Angle.Between(e.x, e.y, this.player.x, this.player.y);
        this.physics.velocityFromRotation(ang, e.speed, e.body.velocity);
        e.setFlipX(this.player.x < e.x);
      } else if (e.body.velocity.length() < 6) {
        e.setVelocity(Phaser.Math.Between(-45, 45), Phaser.Math.Between(-45, 45));
      }
    });
  }
}

// Estado del D-pad táctil (lo escribe la UI, lo lee el bucle de movimiento).
window.LegendInput = window.LegendInput || { up: false, down: false, left: false, right: false };

const GAME_CONFIG = {
  type: Phaser.AUTO,
  parent: 'game-container',
  backgroundColor: '#0f0b14',
  pixelArt: true,
  // Escala responsiva: se adapta a móvil/tablet manteniendo la proporción.
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
    width: 832,
    height: 576,
  },
  physics: { default: 'arcade', arcade: { gravity: { y: 0 }, debug: false } },
  scene: [RoomScene],
};
