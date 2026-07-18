/* Capa de interfaz (HTML overlays) sobre el canvas de Phaser.
   Gestiona login, HUD, batalla (ejercicio) y tienda del empollón. */
const UI = (() => {
  const $ = (id) => document.getElementById(id);

  const state = {
    topics: [],
    currentExercise: null,
    currentEnemy: null,
    isRetry: false,
    onBattleEnd: null,   // callback(defeated:boolean)
  };

  // Renderiza Markdown + LaTeX. Protege las expresiones $...$ / $$...$$ del parser
  // Markdown (para que no se coma los _ y * de las fórmulas) y luego aplica KaTeX.
  const KATEX_OPTS = {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '$', right: '$', display: false },
      { left: '\\(', right: '\\)', display: false },
      { left: '\\[', right: '\\]', display: true },
    ],
    throwOnError: false,
  };
  function renderRich(el, text, inline) {
    if (!el) return;
    if (!text) { el.innerHTML = ''; return; }
    const math = [];
    let s = String(text).replace(
      /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)/g,
      (m) => { math.push(m); return `@@MATH${math.length - 1}@@`; });
    let html;
    if (window.marked) {
      html = inline ? window.marked.parseInline(s) : window.marked.parse(s, { breaks: true });
    } else {
      html = s.replace(/\n/g, '<br>');
    }
    html = html.replace(/@@MATH(\d+)@@/g, (_m, i) => math[+i]);
    el.innerHTML = html;
    if (window.renderMathInElement) {
      try { window.renderMathInElement(el, KATEX_OPTS); } catch (_) {}
    }
  }

  let toastTimer = null;
  function toast(msg) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.add('hidden'), 3000);
  }

  function setStats(stats) {
    if (!stats) return;
    if (stats.available_points !== undefined) $('hud-points').textContent = stats.available_points;
    if (stats.current_streak !== undefined) $('hud-streak').textContent = stats.current_streak;
    if (stats.available_points !== undefined) $('shop-points').textContent = stats.available_points;
  }

  function setRoom(name, tier) {
    const lvl = document.getElementById('hud-level');
    const rn = document.getElementById('hud-roomname');
    if (lvl) lvl.textContent = (tier || 0) + 1;
    if (rn) rn.textContent = name || '';
  }

  function setCandies(n) {
    const el = document.getElementById('hud-candy');
    if (el) el.textContent = n || 0;
  }

  // ---- Mando virtual táctil (D-pad) ----
  function isTouchDevice() {
    return window.matchMedia('(pointer: coarse)').matches ||
           'ontouchstart' in window || navigator.maxTouchPoints > 0;
  }
  function clearDpad() {
    window.LegendInput = window.LegendInput || {};
    ['up', 'down', 'left', 'right'].forEach((d) => { window.LegendInput[d] = false; });
    document.querySelectorAll('#touch-controls .dbtn').forEach((b) => b.classList.remove('active'));
  }
  function initTouch() {
    window.LegendInput = window.LegendInput || { up: false, down: false, left: false, right: false };
    window.LegendUI = window.LegendUI || {};
    window.LegendUI.clearDpad = clearDpad;
    const tc = document.getElementById('touch-controls');
    if (!tc) return false;
    tc.querySelectorAll('.dbtn').forEach((btn) => {
      const dir = btn.dataset.dir;
      const press = (e) => { e.preventDefault(); window.LegendInput[dir] = true; btn.classList.add('active'); };
      const release = (e) => { if (e) e.preventDefault(); window.LegendInput[dir] = false; btn.classList.remove('active'); };
      btn.addEventListener('pointerdown', press);
      btn.addEventListener('pointerup', release);
      btn.addEventListener('pointercancel', release);
      btn.addEventListener('pointerleave', release);
      btn.addEventListener('contextmenu', (e) => e.preventDefault());
    });
    return isTouchDevice();
  }
  function showTouchControls() {
    if (isTouchDevice()) document.getElementById('touch-controls').classList.remove('hidden');
  }

  async function refreshMe() {
    const data = await API.me();
    if (data.success) {
      state.topics = data.topics || [];
      $('hud-user').textContent = data.user.username;
      setStats(data.stats);
    }
    return data;
  }

  // ---------------------------------------------------------------- LOGIN
  function initLogin(onSuccess) {
    const doLogin = async () => {
      const u = $('login-user').value.trim();
      const p = $('login-pass').value;
      $('login-error').textContent = '';
      if (!u || !p) { $('login-error').textContent = 'Rellena usuario y contraseña'; return; }
      const res = await API.login(u, p);
      if (!res.success) { $('login-error').textContent = res.message || 'Error de acceso'; return; }
      $('login-overlay').classList.add('hidden');
      $('hud').classList.remove('hidden');
      await refreshMe();
      onSuccess();
    };
    $('login-btn').addEventListener('click', doLogin);
    $('login-pass').addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin(); });
  }

  // ---------------------------------------------------------------- BATALLA
  const DIFF_LABEL = { easy: 'Fácil', medium: 'Media', hard: 'Difícil' };

  async function startBattle(enemy, onEnd) {
    state.currentEnemy = enemy;
    state.onBattleEnd = onEnd;
    state.isRetry = false;
    state.currentExercise = null;

    $('battle-title').textContent = enemy.title || 'Encuentro';
    const diff = enemy.difficulty || 'medium';
    const badge = $('battle-diff');
    badge.textContent = DIFF_LABEL[diff] || diff;
    badge.className = 'badge ' + diff;

    $('battle-overlay').classList.remove('hidden');
    $('battle-loading').classList.remove('hidden');
    $('battle-body').classList.add('hidden');
    resetBattleControls();

    const res = await API.getExercise(diff);
    if (!res.success) {
      toast(res.message || 'No se pudo generar el ejercicio');
      endBattle(false);
      return;
    }
    state.currentExercise = res.exercise;
    renderExercise(res.exercise);
    $('battle-loading').classList.add('hidden');
    $('battle-body').classList.remove('hidden');
    setTimeout(() => $('battle-answer').focus(), 50);
  }

  function resetBattleControls() {
    state.battleOutcome = null;
    $('battle-answer').value = '';
    $('battle-hint').classList.add('hidden');
    $('battle-hint').textContent = '';
    $('battle-feedback').classList.add('hidden');
    $('battle-feedback').className = 'feedback hidden';
    $('battle-submit-btn').classList.remove('hidden');
    $('battle-submit-btn').disabled = false;
    $('battle-submit-btn').textContent = 'Responder';
    $('battle-continue-btn').classList.add('hidden');
    $('battle-continue-btn').textContent = 'Continuar ▶';
    $('battle-hint-btn').disabled = false;
  }

  function renderExercise(ex) {
    renderRich($('battle-content'), ex.content || '');
    const wrap = $('battle-procedures');
    wrap.innerHTML = '';
    const procs = ex.available_procedures || [];
    $('battle-procedures-wrap').style.display = procs.length ? '' : 'none';
    procs.forEach((p) => {
      const label = document.createElement('label');
      label.className = 'proc';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = p.id;
      const span = document.createElement('span');
      const name = document.createElement('span');
      name.className = 'p-name';
      renderRich(name, p.name || '', true);
      const desc = document.createElement('span');
      desc.className = 'p-desc';
      renderRich(desc, p.description || '', true);
      span.appendChild(name);
      span.appendChild(desc);
      label.appendChild(cb);
      label.appendChild(span);
      wrap.appendChild(label);
    });
  }

  function selectedProcedures() {
    return Array.from(document.querySelectorAll('#battle-procedures input:checked'))
      .map((c) => parseInt(c.value, 10));
  }

  async function submitBattle() {
    const ex = state.currentExercise;
    if (!ex) return;
    const answer = $('battle-answer').value.trim();
    if (!answer) { toast('Escribe una respuesta'); return; }

    const wasRetry = state.isRetry;
    $('battle-submit-btn').disabled = true;
    $('battle-submit-btn').textContent = 'Corrigiendo…';

    const res = await API.submit({
      exercise_id: ex.id,
      answer,
      selected_procedures: selectedProcedures(),
      is_retry: wasRetry,
    });

    if (!res.success) {
      toast(res.message || 'Error al corregir');
      $('battle-submit-btn').disabled = false;
      $('battle-submit-btn').textContent = 'Responder';
      return;
    }

    const ev = res.evaluation;
    setStats({ available_points: ev.available_points, current_streak: ev.current_streak });
    showFeedback(ev);
    const cont = $('battle-continue-btn');

    if (ev.is_correct) {
      // Correcto → el adversario será derrotado (desaparece).
      state.battleOutcome = true;
      $('battle-submit-btn').classList.add('hidden');
      $('battle-hint-btn').disabled = true;
      cont.textContent = '¡Vencido! Continuar ▶';
      cont.classList.remove('hidden');
    } else if (!wasRetry) {
      // Primer fallo: solo puede reintentar (puntos por esfuerzo de MathMentor).
      state.isRetry = true;
      state.battleOutcome = false;
      $('battle-submit-btn').disabled = false;
      $('battle-submit-btn').textContent = 'Reintentar';
    } else {
      // Segundo fallo → termina incorrecto: el adversario solo cambia de posición.
      state.battleOutcome = false;
      $('battle-submit-btn').classList.add('hidden');
      $('battle-hint-btn').disabled = true;
      cont.textContent = 'Continuar ▶';
      cont.classList.remove('hidden');
    }
  }

  function showFeedback(ev) {
    const fb = $('battle-feedback');
    const parts = [];
    parts.push(ev.is_correct ? '✅ ¡Resultado correcto!' : '❌ Resultado incorrecto.');
    if (ev.methodology_feedback) parts.push(ev.methodology_feedback);
    if (ev.feedback) parts.push('\n' + ev.feedback);
    if (ev.streak_bonus) parts.push(`🔥 Bonus de racha: +${ev.streak_bonus}`);
    if (ev.solution) parts.push('📘 **Solución:** ' + ev.solution);
    fb.className = 'feedback ' + (ev.is_correct ? 'ok' : 'bad');
    renderRich(fb, parts.join('\n\n'));
  }

  async function buyHintBattle() {
    const ex = state.currentExercise;
    if (!ex) return;
    $('battle-hint-btn').disabled = true;
    const res = await API.buyHint(ex.id);
    if (!res.success) {
      toast(res.message || 'No se pudo comprar la pista');
      $('battle-hint-btn').disabled = false;
      return;
    }
    const box = $('battle-hint');
    box.classList.remove('hidden');
    // Cada pista se añade como un bloque nuevo debajo del anterior (no lo reemplaza).
    const block = document.createElement('div');
    block.className = 'hint-block';
    box.appendChild(block);
    if (res.hint_type === 'visual') {
      await renderVisualHint(block, res.hint);
    } else {
      renderRich(block, '💡 **Pista ' + (res.hint_level || 1) + ':** ' + res.hint);
    }
    setStats({ available_points: res.available_points });
    if (res.hints_remaining <= 0) $('battle-hint-btn').disabled = true;
    else $('battle-hint-btn').disabled = false;
  }

  // La 2ª pista es un diagrama Mermaid (graph TD ...). Se renderiza a SVG.
  async function renderVisualHint(box, code) {
    box.innerHTML = '';
    const title = document.createElement('div');
    title.className = 'hint-title';
    title.innerHTML = '<span>💡 Esquema visual</span>';
    box.appendChild(title);
    const clean = String(code || '').replace(/```mermaid/gi, '').replace(/```/g, '').trim();
    try {
      if (!window.mermaid) throw new Error('mermaid no disponible');
      const id = 'mmd-' + Date.now();
      const { svg } = await window.mermaid.render(id, clean);
      const wrap = document.createElement('div');
      wrap.className = 'mermaid-svg';
      wrap.innerHTML = svg;
      wrap.title = 'Clic para ampliar';
      wrap.addEventListener('click', () => openDiagram(svg));
      box.appendChild(wrap);
      const zoom = document.createElement('span');
      zoom.className = 'zoom-hint';
      zoom.textContent = '🔍 Clic para ampliar';
      title.appendChild(zoom);
    } catch (e) {
      const pre = document.createElement('pre');
      pre.className = 'hint-pre';
      pre.textContent = clean;
      box.appendChild(pre);
    }
  }

  function openDiagram(svg) {
    $('diagram-content').innerHTML = svg;
    $('diagram-overlay').classList.remove('hidden');
  }
  function closeDiagram() {
    $('diagram-overlay').classList.add('hidden');
    $('diagram-content').innerHTML = '';
  }
  function initDiagram() {
    $('diagram-close-btn').addEventListener('click', closeDiagram);
    $('diagram-overlay').addEventListener('click', (e) => {
      if (e.target === $('diagram-overlay')) closeDiagram(); // clic en el fondo
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$('diagram-overlay').classList.contains('hidden')) closeDiagram();
    });
  }

  function endBattle(defeated) {
    $('battle-overlay').classList.add('hidden');
    const cb = state.onBattleEnd;
    state.onBattleEnd = null;
    if (cb) cb(defeated);
  }

  function initBattle() {
    $('battle-submit-btn').addEventListener('click', submitBattle);
    $('battle-hint-btn').addEventListener('click', buyHintBattle);
    $('battle-continue-btn').addEventListener('click', () => endBattle(state.battleOutcome === true));
  }

  // ---------------------------------------------------------------- TIENDA
  async function openShop() {
    $('shop-overlay').classList.remove('hidden');
    $('shop-summary').classList.add('hidden');
    $('shop-topics').innerHTML = '<p class="tiny">Cargando…</p>';
    // Refresca la propiedad de resúmenes por si cambió en otra sesión.
    await refreshMe();
    openShopSync();
  }

  function sectionTitle(text) {
    const h = document.createElement('div');
    h.className = 'shop-section';
    h.textContent = text;
    return h;
  }

  function shopRow(t) {
    const row = document.createElement('div');
    row.className = 'shop-topic' + (t.owned ? ' owned' : '');

    const label = document.createElement('span');
    label.innerHTML = (t.owned ? '✅ ' : '') + escapeHtml(t.name);
    row.appendChild(label);

    const btn = document.createElement('button');
    btn.className = 'btn ' + (t.owned ? 'ghost' : 'primary-sm');
    btn.textContent = t.owned ? 'Ver · gratis' : 'Comprar · 15 pts';
    btn.addEventListener('click', () => buySummary(t, btn));
    row.appendChild(btn);
    return row;
  }

  async function buySummary(topic, btn) {
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = topic.owned ? 'Abriendo…' : 'Comprando…';
    const res = await API.buySummary(topic.id);
    if (!res.success) {
      toast(res.message || 'No se pudo obtener el resumen');
      btn.disabled = false;
      btn.textContent = original;
      return;
    }
    const box = $('shop-summary');
    const head = `### ${escapeHtml(res.topic_name || topic.name)}\n\n`;
    renderRich(box, head + (res.summary || ''));
    box.classList.remove('hidden');
    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    if (res.available_points !== undefined) setStats({ available_points: res.available_points });
    toast(res.message || 'Resumen obtenido');

    // Marcar como en propiedad y re-pintar la lista (pasa a la sección "Ya en tu poder").
    const t = state.topics.find((x) => x.id === topic.id);
    if (t && !t.owned) { t.owned = true; renderShopList(); }
    else { btn.disabled = false; btn.textContent = original; }
  }

  function renderShopList() {
    // Re-pinta solo la lista conservando el resumen mostrado.
    const summaryVisible = !$('shop-summary').classList.contains('hidden');
    const summaryHtml = $('shop-summary').innerHTML;
    openShopSync();
    if (summaryVisible) {
      $('shop-summary').innerHTML = summaryHtml;
      $('shop-summary').classList.remove('hidden');
    }
  }

  function openShopSync() {
    const wrap = $('shop-topics');
    wrap.innerHTML = '';
    if (!state.topics.length) {
      wrap.innerHTML = '<p class="tiny">No tienes temas asignados.</p>';
      return;
    }
    const owned = state.topics.filter((t) => t.owned);
    const notOwned = state.topics.filter((t) => !t.owned);
    if (owned.length) wrap.appendChild(sectionTitle(`📚 Ya en tu poder (${owned.length}) · acceso gratis`));
    owned.forEach((t) => wrap.appendChild(shopRow(t)));
    if (notOwned.length) wrap.appendChild(sectionTitle('🛒 Disponibles para comprar · 15 pts'));
    notOwned.forEach((t) => wrap.appendChild(shopRow(t)));
  }

  function initShop() {
    $('shop-close-btn').addEventListener('click', () => $('shop-overlay').classList.add('hidden'));
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function isBusy() {
    return !$('battle-overlay').classList.contains('hidden') ||
           !$('shop-overlay').classList.contains('hidden');
  }

  return { initLogin, initBattle, initShop, initDiagram, initTouch, showTouchControls, refreshMe, startBattle, openShop, toast, isBusy, setRoom, setCandies };
})();
