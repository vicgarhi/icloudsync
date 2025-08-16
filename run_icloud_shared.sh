#!/bin/bash
set -euo pipefail

# === Config ===
BASE="/mnt/Data_1/icloud_fotos"
OUT="$BASE/Compartidos"                 # destino
COOKIES="$BASE/cookies"                 # mismas cookies del icloudpd "principal"
LOG="$BASE/logs/icloud_shared.log"
APPLE_ID="victor.garciah@icloud.com"
TZ="Europe/Madrid"
RECENT_DEFAULT=100                      # tras la primera pasada, últimas N
MARKER="$OUT/.full_sync_done"

# === Preparación ===
mkdir -p "$OUT" "$(dirname "$LOG")" "$COOKIES"
# log nuevo en cada ejecución
: > "$LOG"

# A partir de aquí, TODO lo que haga el script se loguea (stdout+stderr)
# (incluye traza de comandos con 'set -x')
{
  echo "[$(date '+%F %T')] Iniciando sincronización de álbumes compartidos…"
  set -x

  # ¿Primera ejecución o incremental?
  if [[ -f "$MARKER" ]]; then
    RECENT_ARGS=(--recent "$RECENT_DEFAULT")
  else
    RECENT_ARGS=()
  fi

  # 1) Listamos álbumes y filtramos SOLO los compartidos
  #    El listados típico incluye una marca "Shared" o similar; capturamos líneas
  #    de compartidos y extraemos el nombre exacto del álbum.
  MAPFILE -t SHARED_ALBUMS < <(
    /usr/bin/docker run --rm \
      -e TZ="$TZ" \
      -v "$COOKIES:/cookies" \
      python:3.11-slim bash -lc '
        set -e
        export DEBIAN_FRONTEND=noninteractive
        apt-get update >/dev/null
        apt-get install -y --no-install-recommends git ca-certificates >/dev/null
        pip install --no-cache-dir --upgrade pip setuptools wheel >/dev/null
        pip install --no-cache-dir "git+https://github.com/icloud-photos-downloader/icloud_photos_downloader.git#egg=icloudpd" >/dev/null
        icloudpd --username "'"$APPLE_ID"'" --cookie-directory /cookies --list-albums
      ' \
    | awk '
        BEGIN{shared=0}
        /Shared/ || /Compartido/ {shared=1}    # marca de sección (según idioma/salida)
        shared && NF>0 {
          # Normalmente el nombre del álbum va tras un separador.
          # Si la línea tiene formato "Shared: Nombre", coger todo tras los dos puntos.
          if (index($0, ":")>0) {
            sub(/^[^:]*:[[:space:]]*/, "", $0)
          }
          print $0
        }' \
    | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
    | grep -v -E '^(Shared|Compartido)s?$' \
    | sort -u
  )

  echo "Álbumes compartidos detectados: ${#SHARED_ALBUMS[@]}"

  # Si no detectó ninguno, salimos elegante
  if [[ ${#SHARED_ALBUMS[@]} -eq 0 ]]; then
    echo "No se detectaron álbumes compartidos en la salida de --list-albums."
    exit 0
  fi

  # 2) Descargamos cada álbum en su propia carpeta {album}/{YYYY/MM}
  for album in "${SHARED_ALBUMS[@]}"; do
    echo "Descargando álbum compartido: [$album]"
    /usr/bin/docker run --rm \
      -e TZ="$TZ" \
      -v "$OUT:/data" \
      -v "$COOKIES:/cookies" \
      python:3.11-slim bash -lc '
        set -e
        export DEBIAN_FRONTEND=noninteractive
        apt-get update >/dev/null
        apt-get install -y --no-install-recommends git ca-certificates >/dev/null
        pip install --no-cache-dir --upgrade pip setuptools wheel >/dev/null
        pip install --no-cache-dir "git+https://github.com/icloud-photos-downloader/icloud_photos_downloader.git#egg=icloudpd" >/dev/null
        icloudpd \
          --username "'"$APPLE_ID"'" \
          --cookie-directory /cookies \
          --directory /data \
          --set-exif-datetime \
          --size original \
          --folder-structure "{album}/{:%Y/%m}" \
          --album "'"$album"'" \
          '"${RECENT_ARGS[@]+"${RECENT_ARGS[@]}"}"'
      '
  done

  # 3) Marcar primera ejecución como completa
  if [[ ! -f "$MARKER" ]]; then
    touch "$MARKER"
  fi

  # 4) Permisos para SMB y legibilidad del log
  chmod -R u=rwX,g=rwX,o=rX "$OUT" || true
  chown truenas_admin:truenas_admin "$LOG" || true
  chmod 664 "$LOG" || true

  set +x
  echo "[$(date '+%F %T')] Fin de sincronización de álbumes compartidos."
} >>"$LOG" 2>&1
