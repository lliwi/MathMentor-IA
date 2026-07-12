# Legend of Maths 🎮⚔️

Interfaz gamificada (2D estilo Zelda, **Phaser 3**) para **MathMentor IA**.
Todo el contenido, la corrección, la puntuación y los usuarios provienen de MathMentor;
este proyecto es un **conector** + cliente de juego y **no modifica el proyecto original**.

Ver [REQUIREMENTS.md](REQUIREMENTS.md) para el diseño completo.

## Arquitectura

```
Navegador (Phaser 3)  ──HTTP/JSON──►  Conector Flask  ──import──►  MathMentor IA
  game/ (canvas + UI)                 connector/                   app/ (intacto)
                                      /api/game/*                  servicios · IA · BBDD
```

- **`connector/`** — App Flask que reutiliza la factory `create_app()` de MathMentor
  (misma BBDD, sesión, login e IA) y le añade el blueprint `/api/game/*`. No se accede a
  la BBDD directamente ni se reimplementa lógica: las vistas JSON de MathMentor
  (`generate_exercise`, `submit_exercise`, `buy_hint`, `buy_summary`) se reutilizan por
  importación. Ver §5.4 de REQUIREMENTS.
- **`game/`** — Cliente Phaser 3 (HTML/JS, sin build). Mundo, jugador, adversarios
  (profesor, abusón, directora), empollón-tienda, y overlays de batalla/tienda.

## Endpoints del conector (`/api/game`)

| Método | Ruta        | Origen en MathMentor            |
|--------|-------------|---------------------------------|
| POST   | `/login`    | modelo `User` + flask_login (nuevo) |
| POST   | `/logout`   | flask_login (nuevo)             |
| GET    | `/me`       | `ScoringService` + temas (nuevo)|
| POST   | `/exercise` | `student.generate_exercise`     |
| POST   | `/submit`   | `student.submit_exercise`       |
| POST   | `/hint`     | `student.buy_hint`              |
| POST   | `/summary`  | `student.buy_summary`           |

## Cómo ejecutar

Requiere el stack de MathMentor (mismo repositorio padre) con su `.env`
(`DATABASE_URL`, claves de IA, `SECRET_KEY`) y PostgreSQL/pgvector accesible.

### Opción A — Docker (recomendada)
Levanta el conector junto al stack existente con un override de compose que **no toca** el
`docker-compose.yml` original (reutiliza su imagen, red y `.env`):
```bash
# desde la raíz del proyecto nomasceros.es
docker compose up -d                                  # arranca MathMentor (db, redis, web)
docker compose -f docker-compose.yml \
  -f "Legend off maths/docker-compose.legend.yml" up -d legend
# Juego:  http://localhost:5055/legend
```

### Opción B — local (entorno Python con las dependencias de MathMentor)
```bash
# con PostgreSQL accesible según el DATABASE_URL del .env (p. ej. localhost:5432)
python "Legend off maths/connector/run.py"
# Juego:  http://localhost:5055/legend
```

Variables opcionales: `LEGEND_PORT` (por defecto `5055`).

## Controles
- **Mover:** flechas o WASD.
- **Adversario:** tócalo → aparece un ejercicio; acierta para vencerlo, o huye.
- **Empollón (🤓):** tócalo → tienda de resúmenes (15 pts). Las pistas (5 pts) se
  compran dentro de cada batalla.

## Notas
- Cliente y conector comparten origen, así que la cookie de sesión funciona sin CORS.
- Los puntos mostrados siempre reflejan MathMentor (fuente única de verdad).
- Login: usa una cuenta con rol `student` de MathMentor.
