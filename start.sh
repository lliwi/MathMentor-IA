#!/usr/bin/env bash
#
# start.sh - Inicia el stack de MathMentor IA
#
# - Levanta los servicios con Docker Compose (db, redis, bgutil-pot, web)
# - Espera a que la base de datos esté lista
# - Aplica las migraciones de Alembic si es necesario (flask db upgrade)
# - Opcionalmente inicializa la BD con usuarios de prueba (--init-db)
#
# Uso:
#   ./start.sh              Inicia el proyecto y aplica migraciones pendientes
#   ./start.sh --build      Reconstruye las imágenes antes de iniciar
#   ./start.sh --init-db    Ejecuta init_db.py tras las migraciones (usuarios de prueba)
#

set -euo pipefail

cd "$(dirname "$0")"

# Detecta el comando de compose disponible (docker compose vs docker-compose)
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "Error: no se encontró 'docker compose' ni 'docker-compose'." >&2
    exit 1
fi

BUILD=false
INIT_DB=false
for arg in "$@"; do
    case "$arg" in
        --build)   BUILD=true ;;
        --init-db) INIT_DB=true ;;
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

# Verifica que exista el fichero .env
if [ ! -f .env ]; then
    echo "Aviso: no existe .env. Copiando desde .env.example..."
    cp .env.example .env
    echo "Revisa .env y configura tus claves de API antes de usar la aplicación."
fi

echo "==> Levantando servicios..."
if [ "$BUILD" = true ]; then
    $COMPOSE up -d --build
else
    $COMPOSE up -d
fi

echo "==> Esperando a que la base de datos esté lista..."
until $COMPOSE exec -T db pg_isready -U mathmentor_user -d mathmentor >/dev/null 2>&1; do
    printf '.'
    sleep 2
done
echo " OK"

# Ejecuta una consulta SQL en el contenedor de la BD y devuelve el valor limpio
db_query() {
    $COMPOSE exec -T db psql -U mathmentor_user -d mathmentor -tAc "$1" 2>/dev/null | tr -d '[:space:]'
}

echo "==> Comprobando estado de migraciones..."
# ¿Existe la tabla alembic_version y tiene una versión registrada?
VERSION_COUNT=0
if [ -n "$(db_query "SELECT to_regclass('public.alembic_version');")" ]; then
    VERSION_COUNT=$(db_query "SELECT count(*) FROM alembic_version;")
fi
# ¿Hay tablas de la aplicación ya creadas (por la auto-inicialización)?
APP_TABLES=$(db_query "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name <> 'alembic_version';")

if [ "${VERSION_COUNT:-0}" -ge 1 ]; then
    echo "==> Aplicando migraciones pendientes (flask db upgrade)..."
    $COMPOSE exec -T web flask db upgrade
elif [ "${APP_TABLES:-0}" -ge 1 ]; then
    # El esquema ya existe (creado por create_all al arrancar) pero sin sello de
    # Alembic. Lo adoptamos como base con 'stamp head' para evitar el error
    # "relation already exists" y luego aplicamos lo que pudiera faltar.
    echo "==> Esquema existente sin sello de Alembic; ejecutando 'flask db stamp head'..."
    $COMPOSE exec -T web flask db stamp head
    $COMPOSE exec -T web flask db upgrade
else
    echo "==> Base de datos vacía; creando esquema con migraciones (flask db upgrade)..."
    $COMPOSE exec -T web flask db upgrade
fi

if [ "$INIT_DB" = true ]; then
    echo "==> Inicializando base de datos con usuarios de prueba..."
    $COMPOSE exec -T web python init_db.py
fi

echo ""
echo "==> MathMentor IA está en marcha."
echo "    Aplicación:  http://localhost:5000"
echo "    Logs:        $COMPOSE logs -f web"
