#!/bin/sh
set -e
umask 002
export TZ=${TZ:-Europe/Madrid}

# Asegura estructura de carpetas en los volúmenes montados
mkdir -p /data /data/Compartidos /data/Albums /cookies /logs

# Ejecuta sync all (library + shared + albums)
icloudsync sync all \
  --out /data \
  --cookies /cookies \
  --folder-template "{:%Y/%m}" \
  --shared-folder-template "{album}/{:%Y/%m}" \
  >> /logs/icloud_all.log 2>&1
