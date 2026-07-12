/* Arranque: inicializa la UI, gestiona el login y lanza Phaser al entrar. */
(function () {
  let game = null;

  function startGame() {
    if (game) return;
    game = new Phaser.Game(GAME_CONFIG);
    // Refresca puntos/racha periódicamente por si cambian fuera de batalla.
    setInterval(() => { if (!UI.isBusy()) UI.refreshMe(); }, 20000);
  }

  document.addEventListener('DOMContentLoaded', async () => {
    UI.initBattle();
    UI.initShop();
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
