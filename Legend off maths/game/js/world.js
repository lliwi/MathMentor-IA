/* Mundo 2D top-down (estilo Zelda) con Phaser 3.
   Un aula con el estudiante (jugador), adversarios y el empollón (NPC-tienda).
   El contacto con un adversario lanza un ejercicio real de MathMentor IA. */
class WorldScene extends Phaser.Scene {
  constructor() { super('WorldScene'); }

  preload() {
    // Texturas generadas en runtime (sin assets externos).
    this.makeRect('tile_floor', 32, 32, 0x3d3054, 0x342847);
    this.makeRect('tile_wall', 32, 32, 0x6b568c, 0x51406e);
    this.makeSprite('player', 0x4ecb71);   // estudiante = verde
    this.makeSprite('teacher', 0xff5d6c);   // profesor = rojo
    this.makeSprite('bully', 0xff9f43);     // abusón = naranja
    this.makeSprite('director', 0x9b5cff);  // director/a = morado
    this.makeSprite('nerd', 0x4aa3ff);      // empollón = azul
  }

  makeRect(key, w, h, fill, border) {
    const g = this.make.graphics({ x: 0, y: 0, add: false });
    g.fillStyle(fill, 1); g.fillRect(0, 0, w, h);
    g.lineStyle(1, border, 1); g.strokeRect(0, 0, w, h);
    g.generateTexture(key, w, h); g.destroy();
  }

  makeSprite(key, color) {
    const g = this.make.graphics({ x: 0, y: 0, add: false });
    g.fillStyle(0x000000, 0.25); g.fillRoundedRect(3, 26, 26, 6, 3); // sombra
    g.fillStyle(color, 1); g.fillRoundedRect(4, 4, 24, 24, 6);        // cuerpo
    g.fillStyle(0xffffff, 0.9); g.fillCircle(12, 13, 2.5); g.fillCircle(20, 13, 2.5); // ojos
    g.fillStyle(0x000000, 0.8); g.fillCircle(12, 13, 1.2); g.fillCircle(20, 13, 1.2);
    g.generateTexture(key, 32, 32); g.destroy();
  }

  create() {
    const COLS = 20, ROWS = 15, T = 32;
    this.physics.world.setBounds(0, 0, COLS * T, ROWS * T);

    // Suelo
    for (let y = 0; y < ROWS; y++)
      for (let x = 0; x < COLS; x++)
        this.add.image(x * T + T / 2, y * T + T / 2, 'tile_floor');

    // Muros perimetrales
    this.walls = this.physics.add.staticGroup();
    for (let x = 0; x < COLS; x++) { this.addWall(x, 0, T); this.addWall(x, ROWS - 1, T); }
    for (let y = 0; y < ROWS; y++) { this.addWall(0, y, T); this.addWall(COLS - 1, y, T); }
    // Un par de "pupitres" internos como obstáculos
    [[6, 5], [7, 5], [12, 9], [13, 9]].forEach(([x, y]) => this.addWall(x, y, T));

    // Jugador
    this.player = this.physics.add.sprite(3 * T, 3 * T, 'player');
    this.player.setCollideWorldBounds(true).setDamping(true).setDrag(0.0001);
    this.physics.add.collider(this.player, this.walls);

    // Adversarios
    this.enemies = this.physics.add.group();
    this.spawnEnemy('teacher', 10, 3, { title: 'Profesor de Mates', difficulty: 'medium' });
    this.spawnEnemy('bully', 4, 11, { title: 'El Abusón', difficulty: 'easy' });
    this.spawnEnemy('director', 16, 11, { title: 'La Directora', difficulty: 'hard' });
    this.physics.add.collider(this.enemies, this.walls);
    this.physics.add.collider(this.enemies, this.enemies);
    this.physics.add.overlap(this.player, this.enemies, this.onEnemyContact, null, this);

    // Empollón (NPC tienda)
    this.nerd = this.physics.add.staticSprite(16, 3, 'nerd').setPosition(16 * T, 3 * T);
    this.nerd.refreshBody();
    this.add.text(16 * T, 3 * T - 22, '🤓', { fontSize: '16px' }).setOrigin(0.5);
    this.physics.add.overlap(this.player, this.nerd, this.onNerdContact, null, this);

    // Etiquetas
    this.labelEnemies();

    // Controles
    this.cursors = this.input.keyboard.createCursorKeys();
    this.wasd = this.input.keyboard.addKeys('W,A,S,D');

    // Cámara
    this.cameras.main.setBounds(0, 0, COLS * T, ROWS * T);
    this.cameras.main.startFollow(this.player, true, 0.1, 0.1);
    this.cameras.main.setZoom(1.4);

    this.contactCooldown = 0;
  }

  addWall(cx, cy, T) {
    const w = this.walls.create(cx * T + T / 2, cy * T + T / 2, 'tile_wall');
    w.refreshBody();
  }

  spawnEnemy(tex, cx, cy, meta) {
    const T = 32;
    const e = this.enemies.create(cx * T, cy * T, tex);
    e.setCollideWorldBounds(true).setBounce(1);
    e.meta = meta;
    e.homeX = cx * T; e.homeY = cy * T;
    e.setVelocity(Phaser.Math.Between(-40, 40), Phaser.Math.Between(-40, 40));
    return e;
  }

  labelEnemies() {
    this.enemyLabels = [];
    this.enemies.getChildren().forEach((e) => {
      const t = this.add.text(e.x, e.y - 22, e.meta.title, {
        fontSize: '10px', color: '#f2e9ff', backgroundColor: '#00000066', padding: { x: 3, y: 1 },
      }).setOrigin(0.5);
      this.enemyLabels.push({ e, t });
    });
  }

  onEnemyContact(player, enemy) {
    if (UI.isBusy() || this.contactCooldown > this.time.now) return;
    this.freeze(true);
    enemy.setVelocity(0, 0);
    UI.startBattle(enemy.meta, (defeated) => {
      this.freeze(false);
      this.contactCooldown = this.time.now + 1200; // evita re-disparo inmediato
      if (defeated) {
        const lbl = this.enemyLabels.find((l) => l.e === enemy);
        if (lbl) lbl.t.destroy();
        this.tweens.add({ targets: enemy, alpha: 0, scale: 0, duration: 300,
          onComplete: () => enemy.destroy() });
      } else {
        // Huida: empujar al jugador lejos del adversario
        const ang = Phaser.Math.Angle.Between(enemy.x, enemy.y, player.x, player.y);
        player.setPosition(player.x + Math.cos(ang) * 48, player.y + Math.sin(ang) * 48);
        enemy.setVelocity(Phaser.Math.Between(-40, 40), Phaser.Math.Between(-40, 40));
      }
    });
  }

  onNerdContact() {
    if (UI.isBusy() || this.contactCooldown > this.time.now) return;
    this.freeze(true);
    UI.openShop();
    // La tienda no bloquea el mundo tras cerrarse; reactivar al detectar cierre.
    const check = this.time.addEvent({
      delay: 200, loop: true, callback: () => {
        if (document.getElementById('shop-overlay').classList.contains('hidden')) {
          this.freeze(false);
          this.contactCooldown = this.time.now + 800;
          check.remove();
        }
      },
    });
  }

  freeze(on) {
    this.frozen = on;
    if (on) this.player.setVelocity(0, 0);
  }

  update() {
    // Etiquetas siguen a los adversarios
    if (this.enemyLabels) this.enemyLabels.forEach((l) => {
      if (l.e.active) { l.t.setPosition(l.e.x, l.e.y - 22); }
    });

    if (this.frozen) { this.player.setVelocity(0, 0); return; }

    const speed = 170;
    let vx = 0, vy = 0;
    if (this.cursors.left.isDown || this.wasd.A.isDown) vx = -speed;
    else if (this.cursors.right.isDown || this.wasd.D.isDown) vx = speed;
    if (this.cursors.up.isDown || this.wasd.W.isDown) vy = -speed;
    else if (this.cursors.down.isDown || this.wasd.S.isDown) vy = speed;
    this.player.setVelocity(vx, vy);
  }
}

const GAME_CONFIG = {
  type: Phaser.AUTO,
  parent: 'game-container',
  width: 800,
  height: 600,
  backgroundColor: '#0f0b14',
  pixelArt: true,
  physics: { default: 'arcade', arcade: { gravity: { y: 0 }, debug: false } },
  scene: [WorldScene],
};
