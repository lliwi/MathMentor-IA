#!/usr/bin/env bash
#
# start.sh - Inicia el stack de MathMentor IA + Legend of Maths
#
# Modos:
#   --dev    (por defecto) Desarrollo: web en :5000 y el juego (legend) en :5055,
#            sin nginx. Usa docker-compose.yml + la override del conector.
#   --prod   Producción: nginx (:80/:443) + certbot (SSL) enrutando /legend y
#            /api/game al conector. Usa docker-compose.prod.yml.
#
# Opciones (combinables con el modo):
#   --build     Reconstruye las imágenes antes de iniciar
#   --init-db   Ejecuta init_db.py tras las migraciones (usuarios de prueba)
#
# Ejemplos:
#   ./start.sh                 Desarrollo, aplica migraciones pendientes
#   ./start.sh --prod          Producción (nginx + certbot)
#   ./start.sh --prod --build  Producción reconstruyendo imágenes
#

set -euo pipefail
cd "$(dirname "$0")"

# Nombre de proyecto fijo: así dev y prod comparten los mismos volúmenes (datos
# persistentes) y no dependen del nombre del directorio. Cambiar con COMPOSE_PROJECT.
PROJECT="${COMPOSE_PROJECT:-mathmentoria}"

# Detecta el comando de compose disponible (docker compose vs docker-compose)
if docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN=(docker-compose)
else
    echo "Error: no se encontró 'docker compose' ni 'docker-compose'." >&2
    exit 1
fi

MODE=dev
BUILD=false
INIT_DB=false
for arg in "$@"; do
    case "$arg" in
        --dev)               MODE=dev ;;
        --prod|--production)  MODE=prod ;;
        --build)             BUILD=true ;;
        --init-db)           INIT_DB=true ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Argumento desconocido: $arg" >&2
            exit 1
            ;;
    esac
done

# Ficheros compose según el modo
if [ "$MODE" = prod ]; then
    COMPOSE_FILES=(-f docker-compose.prod.yml)
else
    COMPOSE_FILES=(-f docker-compose.yml -f "Legend off maths/docker-compose.legend.yml")
fi

# Wrapper de compose (fija el proyecto y maneja la ruta con espacios de la override)
compose() { "${COMPOSE_BIN[@]}" -p "$PROJECT" "${COMPOSE_FILES[@]}" "$@"; }

# Verifica que exista el fichero .env
if [ ! -f .env ]; then
    echo "Aviso: no existe .env. Copiando desde .env.example..."
    cp .env.example .env
    echo "Revisa .env y configura tus claves de API antes de usar la aplicación."
fi

echo "==> Modo: $MODE"
echo "==> Levantando servicios..."
if [ "$BUILD" = true ]; then
    compose up -d --build
else
    compose up -d
fi

echo "==> Esperando a que la base de datos esté lista..."
until compose exec -T db pg_isready -U mathmentor_user -d mathmentor >/dev/null 2>&1; do
    printf '.'
    sleep 2
done
echo " OK"

# Ejecuta una consulta SQL en el contenedor de la BD y devuelve el valor limpio
db_query() {
    compose exec -T db psql -U mathmentor_user -d mathmentor -tAc "$1" 2>/dev/null | tr -d '[:space:]'
}

echo "==> Comprobando estado de migraciones..."
# ¿Existe la tabla alembic_version y tiene una revisión registrada?
VERSION_COUNT=0
if [ -n "$(db_query "SELECT to_regclass('public.alembic_version');")" ]; then
    VERSION_COUNT=$(db_query "SELECT count(*) FROM alembic_version;")
fi

if [ "${VERSION_COUNT:-0}" -ge 1 ]; then
    # BD ya bajo control de Alembic: aplica las migraciones pendientes.
    echo "==> Aplicando migraciones pendientes (flask db upgrade)..."
    compose exec -T web flask db upgrade
else
    # Sin sello de Alembic: instalación limpia O BD creada por create_all.
    # La app construye el esquema actual COMPLETO con create_all en su primer
    # arranque (auto-inicialización), por lo que NO ejecutamos migraciones desde
    # cero: darían "relation already exists". Adoptamos el esquema como baseline.
    # 'stamp head' no ejecuta DDL, así que es seguro incluso en BD vacía.
    echo "==> Sin sello de Alembic; adoptando el esquema actual (flask db stamp head)..."
    compose exec -T web flask db stamp head
fi

# Red de seguridad + inicialización: create_all es idempotente (solo crea las
# tablas que faltan, nunca altera ni borra las existentes).
echo "==> Verificando esquema (create_all idempotente)..."
compose exec -T web python -c "from app import create_app, db; import app.models; app = create_app(); app.app_context().push(); db.create_all(); print('Esquema verificado')"

if [ "$INIT_DB" = true ]; then
    echo "==> Inicializando base de datos con usuarios de prueba..."
    compose exec -T web python init_db.py
fi

echo ""
if [ "$MODE" = prod ]; then
    echo "==> MathMentor IA (producción) en marcha tras nginx."
    echo "    Web:    https://nomasceros.es/"
    echo "    Juego:  https://nomasceros.es/legend"
    echo "    SSL:    primera vez ejecuta ./init-letsencrypt.sh; certbot renueva solo"
    echo "    Logs:   ${COMPOSE_BIN[*]} -p '$PROJECT' ${COMPOSE_FILES[*]} logs -f web legend nginx"
else
    echo "==> MathMentor IA (desarrollo) en marcha."
    echo "    Web:    http://localhost:5000"
    echo "    Juego:  http://localhost:5055/legend"
    echo "    Logs:   ${COMPOSE_BIN[*]} -p '$PROJECT' ${COMPOSE_FILES[*]} logs -f web legend"
fi
