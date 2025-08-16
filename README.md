icloudsync
=========

CLI en Python 3.11 para sincronizar iCloud Photos (fototeca completa y álbumes compartidos) a un directorio montado (ej. TrueNAS Scale vía Docker), con ejecución idempotente e incremental.

Características
- Fototeca: descarga originales en `/data/{YYYY}/{MM}`.
- Álbumes compartidos: descarga en `/data/Compartidos/{Álbum}/{YYYY}/{MM}`.
- Álbumes no compartidos: descarga en `/data/Albums/{Álbum}/{YYYY}/{MM}` (o la ruta que indiques).
- Incremental con caché de estado (JSON) en `/cookies/.icloudsync/state.json`.
- Logging con rotación a `/logs/icloud_sync.log` y stdout.
- Preparado para cron (wrapper `run_all.sh`).
 - Fecha de modificación (mtime) del archivo igual a la fecha de la foto: usa EXIF `DateTimeOriginal` si existe, y si no, la fecha de creación del asset en iCloud.

Instalación (Docker)
1. Construir imagen: `docker build -t icloudsync:latest .`
2. Autenticación inicial (interactiva):
   docker run --rm -it \
     -v /mnt/Data_1/icloud_fotos/cookies:/cookies \
     -e TZ=Europe/Madrid icloudsync:latest \
     auth --apple-id "tu.apple.id@icloud.com"
3. Sincronizar todo (para cron):
   docker run --rm \
     -v /mnt/Data_1/icloud_fotos:/data \
     -v /mnt/Data_1/icloud_fotos/cookies:/cookies \
     -v /mnt/Data_1/icloud_fotos/logs:/logs \
     -e TZ=Europe/Madrid icloudsync:latest \
     sync all --out /data --cookies /cookies

CLI
- `icloudsync auth --apple-id EMAIL --cookies /cookies` genera/renueva cookies (2FA si hace falta).
- `icloudsync sync library --out /data --cookies /cookies [--recent N] [--concurrency N] [--folder-template "{:%Y/%m}"]`
- `icloudsync sync shared --out /data/Compartidos --cookies /cookies [--include REGEX] [--exclude REGEX]`
- `icloudsync sync albums --out /data/Albums --cookies /cookies [--include REGEX] [--exclude REGEX]`
- `icloudsync sync all --out /data --cookies /cookies` (ejecuta library, shared y albums)
- `icloudsync list-albums [--shared-only]`
- `icloudsync doctor`

Configuración
- Por variables de entorno y YAML opcional (`--config`), con precedencia: CLI > env > YAML > defaults.
- Variables: `APPLE_ID`, `TIMEZONE`, `OUT_MAIN`, `OUT_SHARED`, `COOKIES_DIR`, `LOG_FILE`, `FOLDER_TEMPLATE_LIBRARY`, `FOLDER_TEMPLATE_SHARED`, `RECENT`, `CONCURRENCY`, `RETRY_MAX`, `RETRY_BACKOFF`, `UMASK`.

Notas
- Este proyecto utiliza `pyicloud-ipd` para acceder a la API de iCloud Photos. Asegúrate de usar cookies válidas para ejecución no interactiva.
- Para permisos SMB correctos, ajusta `--chown UID:GID` si ejecutas como root dentro del contenedor y verifica `umask` (002 por defecto).

Ejemplos
- Álbumes compartidos en subcarpetas por álbum:
  `docker run --rm -v /mnt/.../Compartidos:/data -v /mnt/.../cookies:/cookies icloudsync:latest sync shared --out /data --cookies /cookies`
- Álbumes no compartidos en subcarpetas por álbum:
  `docker run --rm -v /mnt/.../Albums:/data -v /mnt/.../cookies:/cookies icloudsync:latest sync albums --out /data --cookies /cookies`

Cron (TrueNAS)
- Usa el wrapper `run_all.sh` incluido para crear las carpetas necesarias y ejecutar `sync all` de una vez (library + shared + albums):

  docker run --rm \
    --entrypoint /usr/local/bin/run_all.sh \
    -e TZ=Europe/Madrid \
    -v /mnt/Data_1/icloud_fotos:/data \
    -v /mnt/Data_1/icloud_fotos/cookies:/cookies \
    -v /mnt/Data_1/icloud_fotos/logs:/logs \
    ghcr.io/vicgarhi/icloudsync:latest

  Esto creará `/data/Compartidos` y `/data/Albums` si no existen y volcará el log en `/logs/icloud_all.log`.
