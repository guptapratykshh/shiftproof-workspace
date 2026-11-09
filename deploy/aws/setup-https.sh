#!/usr/bin/env bash
# Run once on the host through SSM, after the stable Elastic IP is attached.
set -euo pipefail
address=$1
contact=$2
mkdir -p /opt/shiftproof/acme
cat > /etc/nginx/conf.d/shiftproof.conf <<EOF
server {
    listen 80;
    server_name $address;
    server_tokens off;
    access_log off;
    location /.well-known/acme-challenge/ { root /opt/shiftproof/acme; }
    location / { return 301 https://$address\$request_uri; }
}
EOF
# The certificate challenge files are public, never the application secrets.
chmod 711 /opt/shiftproof
chmod 755 /opt/shiftproof/acme
systemctl enable --now nginx
/opt/certbot/bin/certbot certonly --non-interactive --agree-tos --email "$contact" \
  --preferred-profile shortlived --webroot --webroot-path /opt/shiftproof/acme \
  --ip-address "$address" --cert-name shiftproof
cat >> /etc/nginx/conf.d/shiftproof.conf <<EOF
server {
    listen 443 ssl;
    http2 on;
    server_name $address;
    server_tokens off;
    access_log off;
    ssl_certificate /etc/letsencrypt/live/shiftproof/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/shiftproof/privkey.pem;
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
nginx -t
systemctl reload nginx
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nnginx -t && systemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/nginx
chmod 700 /etc/letsencrypt/renewal-hooks/deploy/nginx
cat > /etc/systemd/system/shiftproof-certificates.service <<'UNIT'
[Unit]
Description=Renew the public ShiftProof IP certificate
[Service]
Type=oneshot
ExecStart=/opt/certbot/bin/certbot renew --quiet
UNIT
cat > /etc/systemd/system/shiftproof-certificates.timer <<'UNIT'
[Unit]
Description=Check certificate renewal twice daily
[Timer]
OnBootSec=15min
OnUnitActiveSec=12h
RandomizedDelaySec=300
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now shiftproof-certificates.timer
