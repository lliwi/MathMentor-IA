/* Cliente de la API del conector (/api/game/*).
   Toda la lógica real (IA, corrección, puntuación) vive en MathMentor IA. */
const API = (() => {
  const base = '/api/game';

  async function call(path, method = 'GET', body = null) {
    const opts = {
      method,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== null) opts.body = JSON.stringify(body);
    const res = await fetch(base + path, opts);
    let data = {};
    try { data = await res.json(); } catch (_) {}
    data._status = res.status;
    return data;
  }

  return {
    login: (username, password) => call('/login', 'POST', { username, password }),
    logout: () => call('/logout', 'POST'),
    me: () => call('/me', 'GET'),
    getExercise: (difficulty) => call('/exercise', 'POST', { difficulty }),
    submit: (payload) => call('/submit', 'POST', payload),
    buyHint: (exerciseId) => call('/hint', 'POST', { exercise_id: exerciseId }),
    buySummary: (topicId) => call('/summary', 'POST', { topic_id: topicId }),
  };
})();
