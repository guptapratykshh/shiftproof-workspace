#!/usr/bin/env bash
# Add a named address to the existing IP deployment without interrupting it.
# Run through SSM: bash setup-domain.sh HOSTNAME CONTACT_EMAIL ELASTIC_IP
set -euo pipefail
umask 077
domain=$1
contact=$2
address=$3
python3 - "$domain" "$address" <<'PY'
import re, socket, sys
domain, address = sys.argv[1:]
if not re.fullmatch(r'(?=.{1,253}$)[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,63}', domain):
    raise SystemExit('A valid lowercase hostname is required.')
if set(socket.gethostbyname_ex(domain)[2]) != {address}:
    raise SystemExit('The hostname must resolve only to this server Elastic IP.')
PY
exec 9>/opt/shiftproof/https.lock
flock -w 300 9
config=/etc/nginx/conf.d/shiftproof-domain.conf
ip_config=/etc/nginx/conf.d/shiftproof.conf
backup=$(mktemp)
ip_backup=$(mktemp)
candidate=$(mktemp)
cp "$ip_config" "$ip_backup"
had_config=false
if [ -f "$config" ]; then
  cp "$config" "$backup"
  had_config=true
fi
restore() {
  cp "$ip_backup" "$ip_config"
  if "$had_config"; then cp "$backup" "$config"; else rm -f "$config"; fi
  nginx -t && systemctl reload nginx
}
trap 'restore; rm -f "$backup" "$ip_backup" "$candidate"' ERR
trap 'rm -f "$backup" "$ip_backup" "$candidate"' EXIT
mkdir -p /opt/shiftproof/acme
chmod 711 /opt/shiftproof
chmod 755 /opt/shiftproof/acme
# The existing IP virtual host already serves HTTP challenges for new names.
# Keep its working HTTPS listener while issuing the new certificate.
/opt/certbot/bin/certbot certonly --non-interactive --agree-tos --email "$contact" \
  --webroot --webroot-path /opt/shiftproof/acme \
  --domain "$domain" --cert-name shiftproof-domain --keep-until-expiring
cat > "$candidate" <<EOF
server {
    listen 80;
    server_name $domain;
    server_tokens off;
    access_log off;
    location /.well-known/acme-challenge/ { root /opt/shiftproof/acme; }
    location / { return 301 https://$domain\$request_uri; }
}
server {
    listen 443 ssl;
    http2 on;
    server_name $domain;
    server_tokens off;
    access_log off;
    ssl_certificate /etc/letsencrypt/live/shiftproof-domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/shiftproof-domain/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 26m;
    client_body_timeout 30s;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_buffering off;
        proxy_read_timeout 320s;
    }
}
EOF
install -m 644 "$candidate" "$config"
# IP clients often omit SNI. Serve their IP certificate by default even when
# nginx loads the alphabetically earlier domain configuration first.
python3 - "$ip_config" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
path.write_text(path.read_text().replace('listen 443 ssl;', 'listen 443 ssl default_server;'))
PY
nginx -t
systemctl reload nginx
# The existing renewal hook reloads nginx after renewing either certificate.
systemctl enable --now shiftproof-certificates.timer
trap - ERR
printf 'HTTPS configured: https://%s\n' "$domain"
