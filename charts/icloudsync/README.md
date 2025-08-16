## iCloudSync – TrueNAS SCALE App (Helm Chart)

Este chart despliega un CronJob que ejecuta `icloudsync` diariamente para sincronizar:
- Fototeca a `/data/{YYYY}/{MM}`
- Álbumes compartidos a `/data/Compartidos/{Álbum}/{YYYY}/{MM}`
- Álbumes no compartidos a `/data/Albums/{Álbum}/{YYYY}/{MM}`

Requisitos
- Generar cookies 2FA una vez (fuera del cron):
  docker run --rm -it \
    -v /mnt/Data_1/icloud_fotos/cookies:/cookies \
    -e TZ=Europe/Madrid ghcr.io/vicgarhi/icloudsync:latest \
    auth --apple-id "tu@icloud.com"
- Directorios host existentes y escribibles: datasets para `/data`, `/cookies`, `/logs`.

Instalación desde Catalog en TrueNAS
- Apps → Manage Catalogs → Add Catalog → apunta a este repo.
- Instala la app `icloudsync`.
- Rellena:
  - Imagen: `ghcr.io/vicgarhi/icloudsync:latest` (o `:v0.1.0`).
  - Schedule: `0 3 * * *` (ajusta a tu horario).
  - TZ: `Europe/Madrid`.
  - APPLE_ID: tu Apple ID.
  - Storage (hostPath): datasets para `data`, `cookies`, `logs`.
- Despliega. Ver logs en el Job/CronJob y en `/logs/icloud_all.log`.

Instalación con Helm CLI
- helm install icloudsync charts/icloudsync -f charts/icloudsync/values.example.yaml --set env.APPLE_ID=tu@icloud.com

Actualización
- Cambia el tag de la imagen en los valores (`image.tag`) y aplica el upgrade desde Apps o con `helm upgrade`.

Desinstalación
- Elimina la app desde Apps o `helm uninstall icloudsync`. Los datos permanecen en los datasets host.

Notas
- El CronJob ejecuta `/usr/local/bin/run_all.sh`, que crea las carpetas necesarias y ejecuta `sync all`.
- Permisos SMB: el contenedor usa `umask 002`; ajusta `--chown` si ejecutas como root y necesitas fijar propietario.
- Si caduca la sesión 2FA, vuelve a ejecutar el comando `auth` para regenerar cookies.

