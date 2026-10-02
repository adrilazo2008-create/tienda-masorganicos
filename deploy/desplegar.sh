#!/bin/bash
# Despliega este repo en UNA app de cPanel (Passenger). Lo llama .cpanel.yml
# una vez por cada app (tienda y landing comparten código, cada una con su .env).
#   uso: bash deploy/desplegar.sh <carpeta-de-la-app> <pip-del-virtualenv>
#
# Los JSON que se editan desde /admin se guardan en app/data/ de producción;
# `cp -R app` los pisaría con la copia del repo (apagando el popup, la receta,
# etc. en cada deploy), así que se respaldan y se restauran.
set -e
D="$1"
PIP="$2"
KEEP="$(mktemp -d)"
EDITABLES="carrusel_home home integraciones receta_semana popup_home"

/bin/mkdir -p "$D/tmp"
for f in $EDITABLES; do
  if [ -f "$D/app/data/$f.json" ]; then cp -p "$D/app/data/$f.json" "$KEEP/"; fi
done

cp -R app "$D/"
cp passenger_wsgi.py requirements.txt "$D/"

for f in $EDITABLES; do
  if [ -f "$KEEP/$f.json" ]; then cp -p "$KEEP/$f.json" "$D/app/data/"; fi
done
rm -rf "$KEEP"

"$PIP" install -r "$D/requirements.txt"
touch "$D/tmp/restart.txt"
