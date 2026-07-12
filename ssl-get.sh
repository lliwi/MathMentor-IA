#!/bin/bash

# Script manual paso a paso para obtener certificado SSL
# Usa este script si init-letsencrypt.sh falló

echo "=========================================="
echo "OBTENCIÓN MANUAL DE CERTIFICADO SSL"
echo "=========================================="
echo ""

# Detectar si usar docker-compose o docker compose
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "Error: Ni 'docker-compose' ni 'docker compose' están disponibles."
    exit 1
fi

echo "Usando: $DOCKER_COMPOSE"
echo ""

# Configuración
DOMAIN="nomasceros.es"
EMAIL="" # CAMBIA ESTO POR TU EMAIL

if [ -z "$EMAIL" ]; then
    echo "⚠️  ADVERTENCIA: No has configurado un email"
    echo "Edita este script y añade tu email en la variable EMAIL"
    echo ""
    read -p "¿Continuar sin email? (no recomendado) [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    EMAIL_ARG="--register-unsafely-without-email"
else
    EMAIL_ARG="--email $EMAIL"
fi

echo "Paso 1: Creando directorios necesarios..."
mkdir -p ./certbot/conf
mkdir -p ./certbot/www
echo "✓ Directorios creados"
echo ""

echo "Paso 2: Verificando que Nginx está corriendo..."
$DOCKER_COMPOSE ps nginx
if [ $? -ne 0 ]; then
    echo "⚠️  Nginx no está corriendo. Iniciando..."
    $DOCKER_COMPOSE up -d nginx
    sleep 5
fi
echo "✓ Nginx corriendo"
echo ""

echo "Paso 3: Creando archivo de prueba para Let's Encrypt..."
mkdir -p ./certbot/www/.well-known/acme-challenge/
echo "test" > ./certbot/www/.well-known/acme-challenge/test.txt
echo "✓ Archivo de prueba creado"
echo ""

echo "Paso 4: Probando acceso HTTP..."
echo "Probando: http://$DOMAIN/.well-known/acme-challenge/test.txt"
curl -I http://$DOMAIN/.well-known/acme-challenge/test.txt
if [ $? -ne 0 ]; then
    echo "❌ ERROR: No se puede acceder al servidor via HTTP"
    echo "Verifica que:"
    echo "  1. El dominio $DOMAIN apunta a este servidor"
    echo "  2. El puerto 80 está abierto en el firewall"
    echo "  3. Nginx está configurado correctamente"
    exit 1
fi
echo "✓ Acceso HTTP funcionando"
echo ""

echo "Paso 5: Solicitando certificado a Let's Encrypt..."
echo "Dominios: $DOMAIN www.$DOMAIN"
echo ""

# Usar modo staging para pruebas (quita --staging para producción)
# STAGING_ARG="--staging"
STAGING_ARG=""

$DOCKER_COMPOSE run --rm certbot certonly \
    --webroot \
    -w /var/www/certbot \
    $EMAIL_ARG \
    -d $DOMAIN \
    -d www.$DOMAIN \
    --rsa-key-size 4096 \
    --agree-tos \
    --non-interactive \
    --verbose \
    $STAGING_ARG

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ ¡CERTIFICADO OBTENIDO EXITOSAMENTE!"
    echo "=========================================="
    echo ""
    echo "Los certificados están en:"
    echo "  ./certbot/conf/live/$DOMAIN/"
    echo ""
    echo "Archivos generados:"
    ls -lh ./certbot/conf/live/$DOMAIN/
    echo ""
    echo "Siguiente paso:"
    echo "  1. Edita nginx/conf.d/nomasceros.conf"
    echo "  2. Descomenta el bloque 'server' del puerto 443 (HTTPS)"
    echo "  3. Reinicia nginx: $DOCKER_COMPOSE restart nginx"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "❌ ERROR AL OBTENER CERTIFICADO"
    echo "=========================================="
    echo ""
    echo "Revisa los logs arriba para ver el error específico."
    echo ""
    echo "Errores comunes:"
    echo "  1. DNS no apunta correctamente a este servidor"
    echo "  2. Puerto 80 bloqueado por firewall"
    echo "  3. Nginx no puede servir archivos en /.well-known/"
    echo "  4. Límite de tasa de Let's Encrypt alcanzado"
    echo ""
    echo "Para más detalles, revisa:"
    echo "  ./certbot/conf/letsencrypt.log"
    echo ""
    exit 1
fi
