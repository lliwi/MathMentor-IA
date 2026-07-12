/* Generación de texturas por código (sin assets externos): personajes humanoides,
   suelos temáticos (madera, baldosa, césped) y mobiliario (pizarra, pupitres,
   taquillas, árboles, bancos, canasta, puertas). */
const Sprites = (() => {
  const CW = 28, CH = 36; // tamaño de personaje

  function g(scene) { return scene.make.graphics({ x: 0, y: 0, add: false }); }

  // -------- Personaje humanoide --------
  function character(scene, key, o) {
    if (scene.textures.exists(key)) return;
    const gr = g(scene);
    const skin = o.skin || 0xf1c27d;
    // sombra
    gr.fillStyle(0x000000, 0.22); gr.fillRoundedRect(5, CH - 4, 18, 4, 2);
    // piernas + zapatos
    gr.fillStyle(o.pants || 0x33405a, 1); gr.fillRect(9, CH - 11, 4, 8); gr.fillRect(15, CH - 11, 4, 8);
    gr.fillStyle(0x1b1b22, 1); gr.fillRect(8, CH - 4, 6, 3); gr.fillRect(14, CH - 4, 6, 3);
    // brazos
    gr.fillStyle(o.shirt, 1); gr.fillRect(4, 15, 4, 9); gr.fillRect(20, 15, 4, 9);
    // cuerpo/camisa
    gr.fillStyle(o.shirt, 1); gr.fillRoundedRect(7, 14, 14, 13, 4);
    // manos
    gr.fillStyle(skin, 1); gr.fillCircle(6, 24, 2); gr.fillCircle(22, 24, 2);
    // corbata
    if (o.tie) { gr.fillStyle(o.tie, 1); gr.fillTriangle(14, 15, 12, 18, 16, 18); gr.fillRect(13, 18, 2, 5); }
    // mochila (tirantes)
    if (o.backpack) { gr.fillStyle(o.backpack, 1); gr.fillRect(9, 14, 2, 12); gr.fillRect(17, 14, 2, 12); }
    // cabeza
    gr.fillStyle(skin, 1); gr.fillCircle(14, 10, 7);
    // pelo
    if (o.hair != null) {
      gr.fillStyle(o.hair, 1);
      gr.fillRoundedRect(7, 2, 14, 7, 3);
      if (o.longHair) { gr.fillRect(7, 8, 3, 6); gr.fillRect(18, 8, 3, 6); }
    }
    // gorro/birrete
    if (o.cap) { gr.fillStyle(o.cap, 1); gr.fillRect(6, 3, 16, 3); gr.fillRect(9, 0, 10, 4); }
    // ojos
    gr.fillStyle(0xffffff, 1); gr.fillCircle(11, 10, 2); gr.fillCircle(17, 10, 2);
    gr.fillStyle(0x14202e, 1); gr.fillCircle(11.4, 10, 1); gr.fillCircle(17.4, 10, 1);
    // gafas
    if (o.glasses) {
      gr.lineStyle(1.4, 0x101418, 1);
      gr.strokeCircle(11, 10, 3); gr.strokeCircle(17, 10, 3); gr.lineBetween(13.5, 10, 14.5, 10);
    }
    // cejas enfadadas (abusón)
    if (o.angry) { gr.lineStyle(2, 0x2c1f1f, 1); gr.lineBetween(8, 6, 13, 8); gr.lineBetween(20, 6, 15, 8); }
    // libro (empollón)
    if (o.book) { gr.fillStyle(0xffcb47, 1); gr.fillRect(3, 22, 8, 6); gr.fillStyle(0xffffff, 1); gr.fillRect(4, 23, 6, 4); }
    gr.generateTexture(key, CW, CH); gr.destroy();
  }

  // -------- Suelos (32x32) --------
  function floorWood(scene, key) {
    if (scene.textures.exists(key)) return;
    const gr = g(scene);
    gr.fillStyle(0x9c6b3f, 1); gr.fillRect(0, 0, 32, 32);
    gr.fillStyle(0x855a34, 1); for (let y = 0; y < 32; y += 8) gr.fillRect(0, y, 32, 1);
    gr.fillStyle(0xa9784a, 0.6); gr.fillRect(0, 2, 32, 1); gr.fillRect(0, 18, 32, 1);
    gr.generateTexture(key, 32, 32); gr.destroy();
  }
  function floorTile(scene, key) {
    if (scene.textures.exists(key)) return;
    const gr = g(scene);
    gr.fillStyle(0xb9bfce, 1); gr.fillRect(0, 0, 32, 32);
    gr.fillStyle(0xa7adbd, 1); gr.fillRect(0, 0, 16, 16); gr.fillRect(16, 16, 16, 16);
    gr.lineStyle(1, 0x8f96a6, 1); gr.strokeRect(0, 0, 32, 32);
    gr.generateTexture(key, 32, 32); gr.destroy();
  }
  function floorGrass(scene, key) {
    if (scene.textures.exists(key)) return;
    const gr = g(scene);
    gr.fillStyle(0x5aa64b, 1); gr.fillRect(0, 0, 32, 32);
    gr.fillStyle(0x4f9942, 1); for (let i = 0; i < 22; i++) gr.fillRect((i * 13) % 30, (i * 7) % 30, 2, 2);
    gr.fillStyle(0x66b556, 1); for (let i = 0; i < 14; i++) gr.fillRect((i * 9 + 4) % 30, (i * 11 + 3) % 30, 2, 2);
    gr.generateTexture(key, 32, 32); gr.destroy();
  }

  // -------- Muros --------
  function wall(scene, key, color, top) {
    if (scene.textures.exists(key)) return;
    const gr = g(scene);
    gr.fillStyle(color, 1); gr.fillRect(0, 0, 32, 32);
    gr.fillStyle(top, 1); gr.fillRect(0, 0, 32, 8);
    gr.lineStyle(1, 0x000000, 0.15); gr.strokeRect(0, 0, 32, 32);
    gr.generateTexture(key, 32, 32); gr.destroy();
  }
  function fence(scene, key) {
    if (scene.textures.exists(key)) return;
    const gr = g(scene);
    gr.fillStyle(0x6f7683, 1); gr.fillRect(0, 0, 32, 32);
    gr.fillStyle(0x878e9c, 1); gr.fillRect(2, 4, 4, 28); gr.fillRect(14, 4, 4, 28); gr.fillRect(26, 4, 4, 28);
    gr.fillRect(0, 6, 32, 4); gr.fillRect(0, 22, 32, 4);
    gr.generateTexture(key, 32, 32); gr.destroy();
  }

  // -------- Mobiliario (tamaños variados) --------
  function build(scene, key, w, h, draw) {
    if (scene.textures.exists(key)) return;
    const gr = g(scene); draw(gr); gr.generateTexture(key, w, h); gr.destroy();
  }

  function furniture(scene) {
    build(scene, 'blackboard', 176, 44, (gr) => {
      gr.fillStyle(0x5a3d24, 1); gr.fillRoundedRect(0, 0, 176, 44, 3);       // marco
      gr.fillStyle(0x1f4034, 1); gr.fillRect(4, 4, 168, 36);                  // pizarra
      gr.lineStyle(2, 0xffffff, 0.55);
      gr.lineBetween(12, 14, 60, 14); gr.lineBetween(12, 24, 44, 24);
      gr.strokeCircle(120, 22, 8); gr.lineBetween(140, 12, 160, 32);
      gr.fillStyle(0xcaa16b, 1); gr.fillRect(4, 40, 168, 4);                  // repisa
    });
    build(scene, 'desk', 36, 30, (gr) => {
      gr.fillStyle(0x2e2740, 1); gr.fillRect(6, 20, 4, 9); gr.fillRect(26, 20, 4, 9); // patas
      gr.fillStyle(0xcaa878, 1); gr.fillRoundedRect(2, 12, 32, 9, 2);         // tablero
      gr.fillStyle(0xb08e5e, 1); gr.fillRect(2, 19, 32, 2);
      gr.fillStyle(0x3a4a63, 1); gr.fillRoundedRect(11, 22, 14, 8, 2);        // silla
    });
    build(scene, 'locker', 26, 54, (gr) => {
      gr.fillStyle(0x2f7f7a, 1); gr.fillRoundedRect(0, 0, 26, 54, 2);
      gr.lineStyle(1, 0x1f5a56, 1); gr.strokeRect(1, 1, 24, 52); gr.lineBetween(0, 27, 26, 27);
      gr.fillStyle(0xdfe6e9, 1); gr.fillRect(20, 12, 3, 3); gr.fillRect(20, 39, 3, 3);
      gr.fillStyle(0x1f5a56, 1); gr.fillRect(6, 8, 14, 2); gr.fillRect(6, 35, 14, 2);
    });
    build(scene, 'tree', 54, 62, (gr) => {
      gr.fillStyle(0x000000, 0.18); gr.fillRoundedRect(16, 58, 22, 4, 2);
      gr.fillStyle(0x6b4a2f, 1); gr.fillRect(24, 34, 8, 26);                   // tronco
      gr.fillStyle(0x2f7d3a, 1); gr.fillCircle(20, 26, 16); gr.fillCircle(36, 24, 15); gr.fillCircle(28, 14, 15);
      gr.fillStyle(0x3a9247, 1); gr.fillCircle(24, 20, 10); gr.fillCircle(33, 28, 8);
    });
    build(scene, 'bench', 52, 22, (gr) => {
      gr.fillStyle(0x2e2740, 1); gr.fillRect(6, 14, 4, 7); gr.fillRect(42, 14, 4, 7);
      gr.fillStyle(0x8a5a2b, 1); gr.fillRoundedRect(0, 6, 52, 6, 2);
      gr.fillStyle(0x9c6b3f, 1); gr.fillRoundedRect(0, 0, 52, 6, 2);
    });
    build(scene, 'hoop', 30, 70, (gr) => {
      gr.fillStyle(0x7c8794, 1); gr.fillRect(13, 24, 4, 46);                   // poste
      gr.fillStyle(0xecf0f1, 1); gr.fillRoundedRect(6, 4, 20, 16, 2);          // tablero
      gr.lineStyle(2, 0xff5d3b, 1); gr.strokeRect(11, 15, 10, 2);             // aro
      gr.lineStyle(1, 0xffffff, 0.8); gr.lineBetween(11, 17, 13, 24); gr.lineBetween(21, 17, 19, 24);
    });
    build(scene, 'plant', 24, 30, (gr) => {
      gr.fillStyle(0x2f7d3a, 1); gr.fillCircle(8, 10, 6); gr.fillCircle(16, 8, 6); gr.fillCircle(12, 14, 6);
      gr.fillStyle(0xb5651d, 1); gr.fillRect(6, 18, 12, 10);
      gr.fillStyle(0x8a4a15, 1); gr.fillRect(6, 18, 12, 3);
    });
    // Puerta (imagen sobre el hueco del muro)
    build(scene, 'door', 32, 40, (gr) => {
      gr.fillStyle(0x3a2d1c, 1); gr.fillRect(0, 0, 32, 40);
      gr.fillStyle(0x8a5a2b, 1); gr.fillRoundedRect(3, 2, 26, 38, 3);
      gr.fillStyle(0x724a24, 1); gr.fillRect(6, 6, 8, 30); gr.fillRect(18, 6, 8, 30);
      gr.fillStyle(0xffcb47, 1); gr.fillCircle(24, 22, 2);
    });
  }

  // -------- Coleccionables --------
  function collectibles(scene) {
    build(scene, 'candy', 20, 14, (gr) => {
      gr.fillStyle(0xff5db1, 1); gr.fillCircle(10, 7, 5);
      gr.fillStyle(0xff8ecb, 1);
      gr.fillTriangle(0, 2, 0, 12, 6, 7); gr.fillTriangle(20, 2, 20, 12, 14, 7);
      gr.fillStyle(0xffffff, 0.8); gr.fillCircle(8, 5, 1.4);
    });
    build(scene, 'star', 18, 18, (gr) => {
      const pts = [];
      for (let i = 0; i < 10; i++) {
        const a = Math.PI / 5 * i - Math.PI / 2;
        const r = i % 2 ? 3.5 : 8.5;
        pts.push(new Phaser.Math.Vector2(9 + Math.cos(a) * r, 9 + Math.sin(a) * r));
      }
      gr.fillStyle(0xffcb47, 1); gr.fillPoints(pts, true);
      gr.fillStyle(0xffffff, 0.7); gr.fillCircle(7, 7, 1.4);
    });
    build(scene, 'gift', 18, 18, (gr) => {
      gr.fillStyle(0xff5d6c, 1); gr.fillRoundedRect(2, 6, 14, 11, 2);
      gr.fillStyle(0x4aa3ff, 1); gr.fillRect(7, 6, 4, 11);
      gr.fillStyle(0x4aa3ff, 1); gr.fillTriangle(9, 6, 4, 1, 9, 4); gr.fillTriangle(9, 6, 14, 1, 9, 4);
      gr.fillStyle(0xffffff, 0.25); gr.fillRect(2, 6, 14, 2);
    });
  }

  function buildAll(scene) {
    // Personajes
    character(scene, 'player', { shirt: 0x4ecb71, pants: 0x2b3a55, hair: 0x5b3a29, backpack: 0x2a6f97 });
    character(scene, 'teacher', { shirt: 0x8a6bd1, pants: 0x2f2740, hair: 0x333333, tie: 0x33405a, glasses: true });
    character(scene, 'bully', { shirt: 0xff9f43, pants: 0x394150, hair: 0x1f1f1f, angry: true });
    character(scene, 'student', { shirt: 0xff5d6c, pants: 0x2b3a55, hair: 0x4a2f1a, longHair: true, backpack: 0x6b4bb5 });
    character(scene, 'director', { shirt: 0x2f3350, pants: 0x22243a, hair: 0x777777, tie: 0xff5d6c, glasses: true, cap: 0x14161f });
    character(scene, 'nerd', { shirt: 0x4aa3ff, pants: 0x33405a, hair: 0x3a2a1a, glasses: true, book: true });
    // Suelos y muros
    floorWood(scene, 'floor_wood'); floorTile(scene, 'floor_tile'); floorGrass(scene, 'floor_grass');
    wall(scene, 'wall_class', 0xcfd6e6, 0xeef1f7);
    wall(scene, 'wall_office', 0x7a6a86, 0x9385a3);
    fence(scene, 'fence');
    furniture(scene);
    collectibles(scene);
  }

  return { buildAll, CW, CH };
})();
