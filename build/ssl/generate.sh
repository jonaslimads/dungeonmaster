#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-dungeonmaster.lan}"
DIR="$(cd "$(dirname "$0")" && pwd)"

openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout "$DIR/key.pem" \
  -out "$DIR/cert.pem" \
  -subj "/C=BR/ST=Sao Paulo/L=Sao Paulo/O=DungeonMaster/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,IP:127.0.0.1,IP:::1"

echo "Generated self-signed cert for '$DOMAIN' in $DIR/"
