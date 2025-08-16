#!/bin/sh
set -e
umask 002
export TZ=${TZ:-Europe/Madrid}

# Este wrapper asume que 'icloudsync' está en PATH dentro del contenedor
icloudsync sync all \
  --out /data \
  --cookies /cookies \
  --folder-template "{:%Y/%m}" \
  --shared-folder-template "{album}/{:%Y/%m}" \
  >> /logs/icloud_all.log 2>&1

