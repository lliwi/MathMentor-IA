#!/bin/bash

# Script para obtener el certificado SSL inicial de Let's Encrypt
# Asegúrate de que el dominio nomasceros.es apunta a tu servidor antes de ejecutar esto

domains=(nomasceros.es www.nomasceros.es)
rsa_key_size=4096
data_path="./certbot"
email="llibert.morreres@gmail.com" # Añade tu email aquí para notificaciones
staging=0 # Cambiar a 1 para usar el servidor de staging de Let's Encrypt (para pruebas)

echo "### Preparando directorios para certbot..."
mkdir -p "$data_path/conf/live/$domains"
mkdir -p "$data_path/www"

echo ""
echo "### Iniciando servicios..."
docker compose up -d nginx

echo ""
echo "### Solicitando certificado SSL para $domains ..."

# Seleccionar el servidor apropiado de Let's Encrypt
if [ $staging != "0" ]; then
  staging_arg="--staging"
  echo "### MODO STAGING ACTIVADO - Certificado no será válido ###"
else
  staging_arg=""
fi

# Habilitar staging si es necesario
domain_args=""
for domain in "${domains[@]}"; do
  domain_args="$domain_args -d $domain"
done

# Opciones de email
case "$email" in
  "") email_arg="--register-unsafely-without-email" ;;
  *) email_arg="--email $email" ;;
esac

# Obtener el certificado
docker-compose run --rm certbot certonly --webroot -w /var/www/certbot \
  $staging_arg \
  $email_arg \
  $domain_args \
  --rsa-key-size $rsa_key_size \
  --agree-tos \
  --force-renewal

echo ""
echo "### Certificado obtenido con éxito! ###"
echo ""
echo "### Ahora debes:"
echo "1. Editar nginx/conf.d/nomasceros.conf"
echo "2. Descomentar la configuración HTTPS (server block con puerto 443)"
echo "3. Comentar o modificar el server block del puerto 80 para redirigir a HTTPS"
echo "4. Reiniciar nginx: docker-compose restart nginx"
echo ""
echo "### Ejemplo de redirección HTTP a HTTPS:"
echo "server {"
echo "    listen 80;"
echo "    listen [::]:80;"
echo "    server_name nomasceros.es www.nomasceros.es;"
echo ""
echo "    location /.well-known/acme-challenge/ {"
echo "        root /var/www/certbot;"
echo "    }"
echo ""
echo "    location / {"
echo "        return 301 https://\$host\$request_uri;"
echo "    }"
echo "}"
