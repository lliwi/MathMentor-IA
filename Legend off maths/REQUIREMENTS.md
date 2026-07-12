# Legend of Maths — Documento de Requisitos

## 1. Visión general

**Legend of Maths** es un juego 2D de acción-aventura, inspirado en *The Legend of Zelda*
pero ambientado en un instituto/escuela. El jugador controla a un estudiante que recorre
aulas, patios y porches enfrentándose a profesores, al director/a y a otros estudiantes
(como el abusón). Cada "encontronazo" con un adversario abre un reto matemático: el jugador
debe **resolver un ejercicio para poder continuar**.

> **Principio fundamental:** Legend of Maths **NO tiene lógica educativa propia**. Es una
> **nueva interfaz gamificada** sobre la aplicación existente **MathMentor IA**. Todo el
> contenido (ejercicios, resúmenes, pistas), el sistema de puntuación y la gestión de
> usuarios se obtienen de MathMentor IA a través de su API. El juego es un **cliente**;
> MathMentor IA es la **fuente de verdad**.

### 1.1 Objetivos
- Aumentar la motivación y el tiempo de práctica mediante una capa de juego.
- Reutilizar íntegramente el motor pedagógico de MathMentor IA (generación de ejercicios,
  corrección con IA, procedimientos, puntos, rachas, pistas, resúmenes).
- No duplicar datos ni lógica de negocio: puntos, progreso y resultados se persisten en
  MathMentor IA.

### 1.2 Público objetivo
Estudiantes de matemáticas (mismo perfil de usuario `student` que ya existe en MathMentor IA).

---

## 2. Alcance

### 2.1 Dentro del alcance
- Cliente de juego 2D (mundo, movimiento, escenarios, personajes, combate-como-ejercicio).
- Autenticación reutilizando las cuentas de MathMentor IA (rol `student`).
- Encuentros con adversarios que lanzan ejercicios reales de MathMentor IA.
- Compra de pistas y resúmenes a los "empollones" gastando puntos reales del estudiante.
- Visualización de puntos, racha y estadísticas provenientes de MathMentor IA.
- Progresión por escenarios/niveles mapeada a temas (`topics`) de MathMentor IA.

### 2.2 Fuera del alcance (lo aporta MathMentor IA)
- Generación de ejercicios y resúmenes (IA / RAG).
- Corrección de respuestas y evaluación de metodología (procedimientos).
- Cálculo y persistencia de puntuación, rachas y estadísticas.
- Gestión de contenido (subida de PDFs, selección de temas por estudiante).
- Alta/gestión de usuarios y roles (admin, teacher, student).

---

## 3. Requisitos funcionales del juego

### 3.1 Mundo y escenarios (2D top-down estilo Zelda)
- **RF-1.** El mundo se compone de escenarios interconectados por puertas/salidas:
  - **Aulas** (clase de mates, laboratorio, biblioteca).
  - **Patios** (recreo, cancha).
  - **Porches / pasillos / conserjería** y despacho del director/a.
- **RF-2.** Movimiento del protagonista en 4/8 direcciones con colisiones contra paredes y
  mobiliario.
- **RF-3.** Cámara que sigue al jugador; transiciones al cambiar de escenario.
- **RF-4.** Cada escenario se asocia a uno o varios **temas** (`topic`) de MathMentor IA,
  de modo que los ejercicios que aparecen sean coherentes con la zona.

### 3.2 Personajes
- **RF-5. Protagonista:** un estudiante configurable (nombre = usuario de MathMentor IA;
  opcionalmente skin/avatar).
- **RF-6. Adversarios:**
  - **Profesores** (dificultad media).
  - **Director/a** (jefe de nivel, dificultad alta).
  - **Otros estudiantes**, p. ej. **el abusón** (dificultad variable).
  - **Empollones/nerds** (NPC no hostiles): venden pistas y resúmenes.
- **RF-7.** Cada tipo de adversario tiene comportamiento básico (patrulla, detección del
  jugador por proximidad/visión, persecución simple).
- **RF-8.** La **dificultad del adversario** se traduce en la **dificultad del ejercicio**
  solicitado a MathMentor IA (`easy` / `medium` / `hard`).

### 3.3 Encuentros y combate = ejercicio
- **RF-9.** Al entrar en contacto con un adversario hostil se inicia un **encuentro**: se
  pausa el mundo y se abre la interfaz de reto.
- **RF-10.** El juego solicita a MathMentor IA un ejercicio del tema/dificultad del
  adversario y muestra:
  - Enunciado (`content`).
  - Campo de respuesta (`answer`).
  - Selección de **procedimientos** mediante checkboxes con tooltip
    (`available_procedures`), tal como en MathMentor IA.
- **RF-11.** Al enviar, el juego llama a MathMentor IA para **corregir**; recibe:
  `is_correct_result`, `is_correct_methodology`, `feedback`, y el desglose de puntos
  (`score_result`, `score_development`, `score_effort`, `total_score`).
- **RF-12. Resolución del encuentro:**
  - **Resultado correcto** → el adversario es "vencido"/superado; el jugador avanza.
  - **Resultado incorrecto** → se muestra el `feedback` didáctico y se permite
    **reintentar** (mapeado al flujo de `is_retry` / puntos por esfuerzo de MathMentor IA).
  - Se pueden definir "vidas"/energía del jugador; agotarlas devuelve a un punto seguro
    (sin penalizar puntuación real más allá de lo que ya calcula MathMentor IA).
- **RF-13.** El **jefe** (director/a) puede requerir superar varios ejercicios seguidos o
  uno de dificultad `hard` para completar el nivel.

### 3.4 Economía del juego (pistas y resúmenes)
- **RF-14.** Los NPC **empollones** ofrecen una tienda donde el estudiante **gasta puntos
  reales** (los `available_points` de MathMentor IA) para comprar:
  - **Pistas** de un ejercicio (nivel 1 = texto, nivel 2 = visual), reutilizando el
    endpoint de compra de pistas (`buy_hint`, coste 5 puntos).
  - **Resúmenes** de un tema (`buy_summary`), reutilizando el flujo existente.
- **RF-15.** El saldo de puntos disponible se consulta y se descuenta **siempre** en
  MathMentor IA; el juego nunca calcula ni almacena saldos por su cuenta.
- **RF-16.** Los resúmenes comprados son consultables dentro del juego (equivalente a
  `my_summaries`) y, si aplica, descargables en PDF (`summary_pdf`).

### 3.5 Progresión y HUD
- **RF-17.** HUD con: puntos disponibles, racha actual (`current_streak`), mejor racha
  (`best_streak`), y progreso del nivel/escenario.
- **RF-18.** La progresión entre zonas puede requerir un mínimo de ejercicios resueltos
  o puntos, siempre leídos de MathMentor IA.
- **RF-19.** Marcador/ranking opcional dentro del juego usando el `scoreboard` existente.

---

## 4. Integración con MathMentor IA

MathMentor IA (Flask + PostgreSQL/pgvector) ya expone la lógica en el blueprint `student`.
El juego debe integrarse mediante una **API (JSON)** sobre esos flujos. Donde hoy existen
vistas que renderizan HTML, se deberá exponer/adaptar el equivalente JSON.

### 4.1 Autenticación y usuarios
- **RI-1.** El login del juego usa las credenciales de MathMentor IA (usuarios con
  `role = 'student'`). Reutilizar el mecanismo de sesión/login existente
  (`app/auth/routes.py`).
- **RI-2.** El juego opera exclusivamente con la identidad del estudiante autenticado; no
  crea usuarios.

### 4.2 Endpoints/flujos a reutilizar (blueprint `student`, `app/student/routes.py`)
| Flujo del juego | Origen en MathMentor IA | Datos clave |
|---|---|---|
| Obtener ejercicio para un encuentro | `generate_exercise` | `content`, `available_procedures`, `difficulty`, `topic_id` |
| Enviar y corregir respuesta | `submit_exercise` | `answer`, `selected_procedures` → `is_correct_result`, `is_correct_methodology`, `feedback`, puntos |
| Prefetch de siguiente ejercicio | `prefetch_next` / `_prefetch_next_exercise_background` | menor latencia entre encuentros |
| Comprar pista al empollón | `buy_hint` | `hint_level` (1/2), coste 5 pts |
| Comprar resumen al empollón | `buy_summary` | resumen de `topic` |
| Ver resúmenes comprados | `my_summaries`, `summary_pdf` | contenido / PDF |
| Puntos, racha y estadísticas (HUD/ranking) | `scoreboard`, `StudentScore` | `available_points`, `current_streak`, `best_streak`, `total_exercises`, `correct_exercises` |

- **RI-3.** El juego **no** reimplementa la puntuación: se aplica en
  `app/services/scoring_service.py` (reglas: +10 resultado, +5 metodología, +3 esfuerzo en
  reintento, coste pista 5, bonus de racha 3→+2, 5→+5, 10→+10, 15→+20).
- **RI-4.** El modelo de datos permanece en MathMentor IA: `Exercise`, `Submission`,
  `StudentScore`, `HintPurchase`, `Summary`, `Topic`, `User`.

### 4.3 Mapeo dominio-juego ↔ MathMentor IA
- **RI-5.** Escenario/zona → `topic_id` (o conjunto de temas asignados al estudiante).
- **RI-6.** Tipo de adversario → `difficulty` del ejercicio.
- **RI-7.** "Derrotar" adversario → `Submission` con `is_correct_result = true`.
- **RI-8.** Reintento tras fallo → `is_retry = true` con `parent_submission_id`.
- **RI-9.** Tienda del empollón → `HintPurchase` / compra de `Summary`.

### 4.4 Contrato de API (a formalizar)
- **RI-10.** Definir endpoints JSON estables (p. ej. bajo `/api/game/...`) que envuelvan los
  flujos anteriores, devolviendo JSON en lugar de HTML, con autenticación de sesión o token.
- **RI-11.** Manejo de errores homogéneo (sin puntos suficientes, sin ejercicios para el
  tema, IA no disponible, etc.) con códigos y mensajes claros para la UI del juego.

---

## 5. Requisitos técnicos

### 5.1 Cliente de juego
- **RT-1.** Motor 2D: **Phaser 3** (decidido). Web/JS, encaja con el frontend Bootstrap/JS
  actual, se sirve desde el mismo despliegue Docker Compose y consume los endpoints JSON de
  MathMentor IA. Al ser un cliente de navegador, **no** puede conectarse a la base de datos
  directamente (ver §5.4).
- **RT-2.** Renderizado tile-based para los escenarios (Tiled o equivalente), sprites para
  personajes, y sistema de colisiones.
- **RT-3.** Arquitectura por estados/escenas: mundo, encuentro (ejercicio), tienda, pausa.
- **RT-4.** Capa de servicio (cliente API) que aísle todas las llamadas a MathMentor IA.

### 5.2 Backend / integración
- **RT-5.** No introducir una segunda base de datos de progreso: la persistencia vive en
  PostgreSQL de MathMentor IA.
- **RT-6.** Reutilizar el despliegue existente (Docker Compose); el juego se sirve como
  frontend adicional o como app estática que consume la API.
- **RT-7.** CORS/CSRF y sesión configurados para permitir el cliente de juego.

### 5.3 Assets
- **RT-8.** Tilesets de escuela (aulas, patios, porches), sprites del estudiante y de
  adversarios (profesor, director/a, abusón, empollón), UI de reto y tienda.
- **RT-9.** Efectos de sonido/música opcionales, con posibilidad de silenciar.

### 5.4 Evaluación: acceso directo a la BBDD vs. capa JSON
**Decisión: se descarta el acceso directo a la base de datos; se usa una capa JSON fina
sobre el Flask existente.** Motivos:

- **Imposibilidad técnica desde el cliente.** Phaser 3 se ejecuta en el navegador y solo
  puede comunicarse por HTTP/WebSocket; **no puede abrir conexiones TCP a PostgreSQL**.
  Además, exponer credenciales de BBDD en el cliente sería un fallo de seguridad crítico.
- **La lógica de negocio no está en la BBDD, está en Python.** No es expresable en SQL:
  - Generación de ejercicios → `app/ai_engines/` + `app/services/rag_service.py`
    (llamadas a OpenAI/DeepSeek/Ollama).
  - Corrección y feedback → IA en Python.
  - Puntuación, rachas y bonus → `app/services/scoring_service.py`.
  - Efectos de compra de pistas/resúmenes → rutas del blueprint `student`.
- **Rompería la fuente única de verdad.** Un backend paralelo atacando la misma BBDD tendría
  que **reimplementar** toda esa lógica, con duplicación y riesgo de desincronización;
  contradice el principio del §1.
- **Escrituras sin validación.** El acceso SQL directo saltaría las validaciones y el
  control anti-trampa (RNF-7).

**Conclusión:** la vía correcta y de menor coste es exponer los flujos existentes del
blueprint `student` como **endpoints JSON dentro del mismo Flask** (§4.4). No es construir
una API nueva desde cero, sino devolver JSON en lugar de HTML reutilizando servicios que ya
existen. (Opcionalmente, datos de solo lectura del HUD como puntos/racha podrían leerse
directo de la BBDD, pero no compensa fragmentar el acceso: se sirven por el mismo endpoint
JSON.)

---

## 6. Requisitos no funcionales
- **RNF-1. Rendimiento:** encuentros fluidos; usar prefetch de ejercicios para minimizar
  esperas de la IA; objetivo 60 FPS en navegador de gama media.
- **RNF-2. Latencia de IA:** mostrar estados de carga durante generación/corrección; usar
  el prefetch en background ya presente en MathMentor IA.
- **RNF-3. Consistencia:** los puntos mostrados en el juego deben coincidir siempre con
  MathMentor IA (fuente única de verdad); refrescar tras cada operación.
- **RNF-4. Seguridad:** no exponer soluciones (`solution` / `expected_procedures`) al
  cliente; la corrección ocurre en el servidor. Las pistas solo se entregan tras el cobro
  real.
- **RNF-5. Accesibilidad:** interfaz de reto legible (fórmulas, tooltips de procedimientos),
  controles reasignables, soporte teclado.
- **RNF-6. Compatibilidad:** navegador moderno de escritorio; deseable soporte táctil/móvil.
- **RNF-7. Integridad (anti-trampa):** el juego nunca otorga puntos sin una `Submission`
  válida corregida en el servidor; toda recompensa deriva de MathMentor IA.

---

## 7. Modelo de datos (referencia — vive en MathMentor IA)
El juego consume, no redefine, estos modelos:
- `Exercise` (`content`, `available_procedures`, `expected_procedures`, `difficulty`,
  `topic_id`, `status`).
- `Submission` (`answer`, `selected_procedures`, `is_correct_result`,
  `is_correct_methodology`, puntuaciones, `feedback`, `is_retry`, `parent_submission_id`).
- `StudentScore` (`total_points`, `available_points`, `current_streak`, `best_streak`,
  estadísticas).
- `HintPurchase` (`hint_level`, `hint_type`, `points_paid`).
- `Summary` (`content`, `topic_id`, `status`).
- `Topic`, `User` (`role='student'`).

---

## 8. Riesgos y consideraciones
- **R-1.** Latencia de generación/corrección por IA puede romper el ritmo de juego →
  mitigar con prefetch y cachés existentes (`cache_service.py`).
- **R-2.** Acoplamiento con vistas HTML actuales → requiere formalizar una API JSON estable
  (sección 4.4) antes de construir el cliente.
- **R-3.** Cobertura de temas: un escenario sin ejercicios disponibles debe tener
  comportamiento definido (fallback a otro tema o mensaje).
- **R-4.** Anti-trampa: todo consumo/otorgamiento de puntos debe validarse en servidor.

---

## 9. Fases sugeridas (roadmap)
1. **Fase 0 — API:** formalizar endpoints JSON (`/api/game/...`) sobre los flujos del
   blueprint `student` (ejercicio, corrección, pistas, resúmenes, puntuación).
2. **Fase 1 — Vertical slice:** un aula, un profesor, un encuentro completo (ejercicio →
   corrección → puntos reales) y HUD de puntos/racha.
3. **Fase 2 — Economía:** NPC empollón con tienda de pistas y resúmenes (gasto de puntos
   reales).
4. **Fase 3 — Contenido:** más escenarios (patios, porches), adversarios (director/a,
   abusón) y jefes de nivel; mapeo de zonas a temas.
5. **Fase 4 — Pulido:** balance de dificultad, accesibilidad, sonido, soporte móvil, ranking.

---

## 10. Criterios de aceptación (MVP)
- **CA-1.** El estudiante inicia sesión con su cuenta de MathMentor IA.
- **CA-2.** Al chocar con un profesor se muestra un ejercicio real generado por MathMentor
  IA, con enunciado y selección de procedimientos.
- **CA-3.** Al responder, la corrección y los puntos provienen de MathMentor IA y se
  reflejan en el HUD; el feedback se muestra al fallar y se permite reintentar.
- **CA-4.** El estudiante puede comprar una pista y/o un resumen a un empollón gastando sus
  puntos reales, con el saldo actualizado en MathMentor IA.
- **CA-5.** El juego no persiste puntuación propia: todos los valores coinciden con
  MathMentor IA tras cada operación.
