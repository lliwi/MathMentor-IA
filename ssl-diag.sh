#!/bin/bash

echo "=========================================="
echo "DIAGNÓSTICO DE CERTIFICADOS SSL"
echo "=========================================="
echo ""

echo "1. Verificando DNS del dominio..."
echo "-----------------------------------"
dig +short nomasceros.es A
dig +short www.nomasceros.es A
echo ""

echo "2. Verificando que Nginx está corriendo..."
echo "-----------------------------------"
docker compose ps nginx
echo ""

echo "3. Verificando puertos abiertos..."
echo "-----------------------------------"
netstat -tulpn | grep -E ':(80|443)' || ss -tulpn | grep -E ':(80|443)'
echo ""

echo "4. Verificando directorio certbot..."
echo "-----------------------------------"
ls -la ./certbot/conf/
ls -la ./certbot/www/
echo ""

echo "5. Verificando logs de certbot..."
echo "-----------------------------------"
if [ -f "./certbot/conf/letsencrypt.log" ]; then
    tail -50 ./certbot/conf/letsencrypt.log
else
    echo "No se encontró archivo de log"
fi
echo ""

echo "6. Probando acceso HTTP al servidor..."
echo "-----------------------------------"
curl -I http://nomasceros.es/.well-known/acme-challenge/test 2>&1 | head -10
echo ""

echo "7. Verificando configuración de Nginx..."
echo "-----------------------------------"
docker compose exec nginx nginx -t
echo ""

echo "8. Logs recientes de nginx..."
echo "-----------------------------------"
docker compose logs --tail=50 nginx
echo ""

echo "=========================================="
echo "FIN DEL DIAGNÓSTICO"
echo "=========================================="
