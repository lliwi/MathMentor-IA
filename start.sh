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
# ¿Existe la tabla alembic_version y tiene una revisión registrada?
VERSION_COUNT=0
if [ -n "$(db_query "SELECT to_regclass('public.alembic_version');")" ]; then
    VERSION_COUNT=$(db_query "SELECT count(*) FROM alembic_version;")
fi

if [ "${VERSION_COUNT:-0}" -ge 1 ]; then
    # BD ya bajo control de Alembic: aplica las migraciones pendientes.
    echo "==> Aplicando migraciones pendientes (flask db upgrade)..."
    $COMPOSE exec -T web flask db upgrade
else
    # Sin sello de Alembic: instalación limpia O BD creada por create_all.
    # La app construye el esquema actual COMPLETO con create_all en su primer
    # arranque (auto-inicialización), por lo que NO ejecutamos migraciones desde
    # cero: darían "relation already exists". Adoptamos el esquema como baseline.
    # 'stamp head' no ejecuta DDL, así que es seguro incluso en BD vacía.
    echo "==> Sin sello de Alembic; adoptando el esquema actual (flask db stamp head)..."
    $COMPOSE exec -T web flask db stamp head
fi

# Red de seguridad + inicialización: create_all es idempotente (solo crea las
# tablas que faltan, nunca altera ni borra las existentes). Cubre dos casos:
#  - Instalación limpia: al construir la app (create_app) se dispara la
#    auto-inicialización, que crea las tablas y siembra el usuario admin.
#  - BD existente a la que le falta alguna tabla de una función nueva
#    (p.ej. 'documents'): la crea sin tocar el resto.
# Va DESPUÉS del upgrade para no colisionar nunca con un CREATE TABLE de una migración.
echo "==> Verificando esquema (create_all idempotente)..."
$COMPOSE exec -T web python -c "from app import create_app, db; import app.models; app = create_app(); app.app_context().push(); db.create_all(); print('Esquema verificado')"

if [ "$INIT_DB" = true ]; then
    echo "==> Inicializando base de datos con usuarios de prueba..."
    $COMPOSE exec -T web python init_db.py
fi

echo ""
echo "==> MathMentor IA está en marcha."
echo "    Aplicación:  http://localhost:5000"
echo "    Logs:        $COMPOSE logs -f web"
