#!/bin/bash
LOG_FILE="/mnt/Data_1/icloud_fotos/logs/icloudpd.log"

# Sobrescribir log en cada ejecución
> "$LOG_FILE"

# Ejecutar icloudpd en el contenedor, limitando a las últimas 100
/usr/bin/docker exec ix-icloudpd-icloudpd-1 /opt/icloudpd/bin/icloudpd \
  --username "victor.garciah@icloud.com" \
  --directory /data \
  --cookie-directory /cookies \
  --set-exif-datetime \
  --size original \
  --folder-structure "{:%Y/%m}" \
  --recent 100 \
  >> "$LOG_FILE" 2>&1
