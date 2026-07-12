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
  }

  function resetBattleControls() {
    $('battle-answer').value = '';
    $('battle-hint').classList.add('hidden');
    $('battle-hint').textContent = '';
    $('battle-feedback').classList.add('hidden');
    $('battle-feedback').className = 'feedback hidden';
    $('battle-submit-btn').classList.remove('hidden');
    $('battle-submit-btn').disabled = false;
    $('battle-submit-btn').textContent = 'Responder';
    $('battle-continue-btn').classList.add('hidden');
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

    $('battle-submit-btn').disabled = true;
    $('battle-submit-btn').textContent = 'Corrigiendo…';

    const res = await API.submit({
      exercise_id: ex.id,
      answer,
      selected_procedures: selectedProcedures(),
      is_retry: state.isRetry,
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

    if (ev.is_correct) {
      $('battle-submit-btn').classList.add('hidden');
      $('battle-hint-btn').disabled = true;
      $('battle-continue-btn').classList.remove('hidden');
    } else {
      // Permitir un reintento (puntos por esfuerzo los gestiona MathMentor)
      state.isRetry = true;
      $('battle-submit-btn').disabled = false;
      $('battle-submit-btn').textContent = 'Reintentar';
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
    renderRich(box, '💡 ' + res.hint);
    box.classList.remove('hidden');
    setStats({ available_points: res.available_points });
    if (res.hints_remaining <= 0) $('battle-hint-btn').disabled = true;
    else $('battle-hint-btn').disabled = false;
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
    $('battle-continue-btn').addEventListener('click', () => endBattle(true));
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

  return { initLogin, initBattle, initShop, refreshMe, startBattle, openShop, toast, isBusy };
})();
