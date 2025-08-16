from __future__ import annotations

import getpass
import logging
import os
from typing import Optional

try:
    from pyicloud_ipd import PyiCloudService
except Exception:  # pragma: no cover - optional at dev time
    PyiCloudService = None  # type: ignore


log = logging.getLogger(__name__)


class AuthError(Exception):
    pass


def login_interactive(apple_id: str, cookies_dir: str, interactive: bool = True) -> int:
    if PyiCloudService is None:
        log.error("pyicloud-ipd no está instalado. Instala dependencias dentro de Docker.")
        return 2

    os.makedirs(cookies_dir, exist_ok=True)
    password = None
    if interactive:
        password = getpass.getpass(prompt=f"Contraseña para {apple_id}: ")

    api = PyiCloudService(apple_id, password=password, cookie_directory=cookies_dir)

    # 2FA moderno
    if getattr(api, "requires_2fa", False):
        if not interactive:
            log.error("Se requiere 2FA pero --interactive no está activo. Abortando.")
            return 3
        log.info("La cuenta requiere 2FA. Introduce el código recibido en tus dispositivos confiables.")
        code = input("Código 2FA: ").strip()
        try:
            if not api.validate_2fa_code(code):  # type: ignore[attr-defined]
                log.error("Código 2FA inválido.")
                return 4
            if not api.is_trusted_session:  # type: ignore[attr-defined]
                api.trust_session()  # type: ignore[attr-defined]
        except AttributeError:
            # Fallback a flujo 2SA (antiguo) por dispositivos
            devices = api.trusted_devices
            device = devices[0]
            if not api.send_verification_code(device):
                log.error("No se pudo enviar el código 2SA.")
                return 5
            code = input("Código 2SA: ").strip()
            if not api.validate_verification_code(device, code):
                log.error("Código 2SA inválido.")
                return 6

    # 2SA antiguo
    elif getattr(api, "requires_2sa", False):
        if not interactive:
            log.error("Se requiere 2SA pero --interactive no está activo. Abortando.")
            return 7
        devices = api.trusted_devices
        log.info("Dispositivos confiables:")
        for i, d in enumerate(devices):
            name = d.get("deviceName") or d.get("phoneNumber") or str(d)
            log.info(f"  [{i}] {name}")
        try:
            idx = int(input("Elige dispositivo para recibir código [0]: ") or "0")
            device = devices[idx]
        except Exception:
            device = devices[0]
        if not api.send_verification_code(device):
            log.error("No se pudo enviar el código 2SA.")
            return 8
        code = input("Código recibido: ").strip()
        if not api.validate_verification_code(device, code):
            log.error("Código 2SA inválido.")
            return 9

    log.info("Autenticación OK y cookies guardadas.")
    return 0


def ensure_noninteractive_session(apple_id: str, cookies_dir: str) -> None:
    if PyiCloudService is None:
        raise AuthError("pyicloud-ipd no está instalado.")
    api = PyiCloudService(apple_id, password=None, cookie_directory=cookies_dir)
    if getattr(api, "requires_2fa", False) or getattr(api, "requires_2sa", False):
        raise AuthError("Sesión no válida: se requiere 2FA/2SA. Ejecuta 'icloudsync auth'.")

