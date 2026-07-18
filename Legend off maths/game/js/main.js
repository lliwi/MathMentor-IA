/* Arranque: inicializa la UI, gestiona el login y lanza Phaser al entrar. */
(function () {
  let game = null;

  function startGame() {
    if (game) return;
    game = new Phaser.Game(GAME_CONFIG);
    window.game = game; // acceso para depuración
    UI.showTouchControls(); // muestra el D-pad en dispositivos táctiles
    // Refresca puntos/racha periódicamente por si cambian fuera de batalla.
    setInterval(() => { if (!UI.isBusy()) UI.refreshMe(); }, 20000);
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (window.mermaid) {
      window.mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });
    }
    UI.initBattle();
    UI.initShop();
    UI.initDiagram();
    UI.initTouch();
    UI.initLogin(startGame);

    // Si ya hay sesión activa (cookie), saltar el login.
    const me = await API.me();
    if (me.success) {
      document.getElementById('login-overlay').classList.add('hidden');
      document.getElementById('hud').classList.remove('hidden');
      await UI.refreshMe();
      startGame();
    }
  });
})();
