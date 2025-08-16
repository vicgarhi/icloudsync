from __future__ import annotations

import logging
import os
import sys
from typing import Optional

import typer

from .config import Config
from .logging_setup import setup_logging
from .auth import login_interactive, ensure_noninteractive_session, AuthError
from .state import StateDB
from .photos import ICloudPhotos, PyiCloudService
from .sync import sync_assets


app = typer.Typer(help="Sincroniza iCloud Photos (fototeca y compartidos)")


def _make_state_path(cookies_dir: str) -> str:
    return os.path.join(cookies_dir, ".icloudsync", "state.json")


def _get_api(apple_id: str, cookies_dir: str):
    if PyiCloudService is None:
        raise typer.Exit(code=2)
    return PyiCloudService(apple_id, password=None, cookie_directory=cookies_dir)


@app.callback()
def main_callback(
    ctx: typer.Context,
    yaml: Optional[str] = typer.Option(None, "--config", help="Ruta a YAML de configuración"),
    log_level: str = typer.Option("INFO", help="Nivel de log (DEBUG, INFO, WARN, ERROR)"),
    no_log_file: bool = typer.Option(False, help="No escribir a fichero de log"),
):
    ctx.obj = {
        "yaml": yaml,
        "log_level": log_level,
        "no_log_file": no_log_file,
    }


@app.command(help="Flujo de autenticación para generar/renovar cookies")
def auth(
    apple_id: Optional[str] = typer.Option(None, "--apple-id", envvar="APPLE_ID", help="Apple ID (email)"),
    cookies: str = typer.Option("/cookies", "--cookies", help="Carpeta de cookies"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Permitir prompts 2FA por consola"),
):
    cfg = Config.merge(yaml_path=None, cli={"APPLE_ID": apple_id})
    setup_logging("INFO", None)

    if not cfg.apple_id:
        typer.echo("Debe proporcionar --apple-id o APPLE_ID.")
        raise typer.Exit(code=1)

    code = login_interactive(cfg.apple_id, cookies, interactive=interactive)
    raise typer.Exit(code=code)


@app.command(help="Listar álbumes; --shared-only para sólo compartidos")
def list_albums(
    apple_id: Optional[str] = typer.Option(None, "--apple-id", envvar="APPLE_ID"),
    cookies: str = typer.Option("/cookies", "--cookies"),
    shared_only: bool = typer.Option(False, "--shared-only", help="Sólo álbumes compartidos"),
):
    cfg = Config.merge(yaml_path=None, cli={"APPLE_ID": apple_id})
    setup_logging("INFO", None)
    if not cfg.apple_id:
        typer.echo("Debe proporcionar --apple-id o APPLE_ID.")
        raise typer.Exit(code=1)
    try:
        ensure_noninteractive_session(cfg.apple_id, cookies)
    except AuthError as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)
    api = _get_api(cfg.apple_id, cookies)
    photos = ICloudPhotos(api)

    if shared_only:
        albums = photos.list_shared_albums()
        for name, _ in albums:
            print(f"[Compartido] {name}")
    else:
        # List regular albums (best effort)
        try:
            for name in api.photos.albums.keys():  # type: ignore[attr-defined]
                print(name)
        except Exception:
            print("No se pudo enumerar álbumes normales.")
        albums = photos.list_shared_albums()
        for name, _ in albums:
            print(f"[Compartido] {name}")


def _merge_common(ctx: typer.Context, cli_overrides: dict) -> Config:
    yaml_path = ctx.obj.get("yaml") if ctx.obj else None
    cfg = Config.merge(yaml_path=yaml_path, cli=cli_overrides)
    setup_logging(cfg.log_level, None if cfg.no_log_file else cfg.log_file)
    return cfg


@app.command(help="Sincroniza la fototeca completa")
def sync_library(
    ctx: typer.Context,
    out: str = typer.Option("/data", "--out", help="Ruta base de descarga"),
    cookies: str = typer.Option("/cookies", "--cookies"),
    recent: Optional[int] = typer.Option(None, "--recent", help="Limitar a últimos N ítems"),
    concurrency: int = typer.Option(4, "--concurrency", help="Descargas paralelas"),
    folder_template: str = typer.Option("{:%Y/%m}", "--folder-template", help="Plantilla de carpetas"),
    dry_run: bool = typer.Option(False, "--dry-run", help="No escribir, sólo listar"),
    chown: Optional[str] = typer.Option(None, "--chown", help="UID:GID para fijar propietario"),
):
    cfg = _merge_common(ctx, {
        "OUT_MAIN": out,
        "COOKIES_DIR": cookies,
        "RECENT": recent,
        "CONCURRENCY": concurrency,
        "FOLDER_TEMPLATE_LIBRARY": folder_template,
        "DRY_RUN": dry_run,
        "CHOWN": chown,
    })

    if not cfg.apple_id:
        typer.echo("Debe proporcionar --apple-id/APPLE_ID via config/env.")
        raise typer.Exit(code=1)
    try:
        ensure_noninteractive_session(cfg.apple_id, cfg.cookies_dir)
    except AuthError as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)

    api = _get_api(cfg.apple_id, cfg.cookies_dir)
    photos = ICloudPhotos(api)
    state = StateDB(_make_state_path(cfg.cookies_dir))
    res = sync_assets(
        assets=photos.iter_library(cfg.recent),
        out_base=cfg.out_main,
        folder_template=cfg.folder_template_library,
        state=state,
        concurrency=cfg.concurrency,
        dry_run=cfg.dry_run,
        umask=cfg.umask,
        chown=cfg.chown,
    )
    logging.info(f"sync library -> {res}")


@app.command(help="Sincroniza álbumes compartidos")
def sync_shared(
    ctx: typer.Context,
    out: str = typer.Option("/data/Compartidos", "--out"),
    cookies: str = typer.Option("/cookies", "--cookies"),
    recent: Optional[int] = typer.Option(None, "--recent"),
    folder_template: str = typer.Option("{album}/{:%Y/%m}", "--folder-template"),
    include: Optional[str] = typer.Option(None, "--include", help="Regex de inclusión"),
    exclude: Optional[str] = typer.Option(None, "--exclude", help="Regex de exclusión"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    chown: Optional[str] = typer.Option(None, "--chown"),
):
    cfg = _merge_common(ctx, {
        "OUT_SHARED": out,
        "COOKIES_DIR": cookies,
        "RECENT": recent,
        "FOLDER_TEMPLATE_SHARED": folder_template,
        "DRY_RUN": dry_run,
        "CHOWN": chown,
    })
    if not cfg.apple_id:
        typer.echo("Debe proporcionar --apple-id/APPLE_ID via config/env.")
        raise typer.Exit(code=1)
    try:
        ensure_noninteractive_session(cfg.apple_id, cfg.cookies_dir)
    except AuthError as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)

    api = _get_api(cfg.apple_id, cfg.cookies_dir)
    photos = ICloudPhotos(api)
    state = StateDB(_make_state_path(cfg.cookies_dir))
    assets = photos.iter_shared(cfg.recent, include=include, exclude=exclude)
    res = sync_assets(
        assets=assets,
        out_base=cfg.out_shared,
        folder_template=cfg.folder_template_shared,
        state=state,
        concurrency=cfg.concurrency,
        dry_run=cfg.dry_run,
        umask=cfg.umask,
        chown=cfg.chown,
    )
    logging.info(f"sync shared -> {res}")


@app.command(help="Sincroniza álbumes NO compartidos en carpetas por álbum")
def sync_albums(
    ctx: typer.Context,
    out: str = typer.Option("/data/Albums", "--out"),
    cookies: str = typer.Option("/cookies", "--cookies"),
    recent: Optional[int] = typer.Option(None, "--recent"),
    folder_template: str = typer.Option("{album}/{:%Y/%m}", "--folder-template"),
    include: Optional[str] = typer.Option(None, "--include", help="Regex de inclusión"),
    exclude: Optional[str] = typer.Option(None, "--exclude", help="Regex de exclusión"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    chown: Optional[str] = typer.Option(None, "--chown"),
):
    cfg = _merge_common(ctx, {
        "OUT_SHARED": out,  # reuse path field for this target
        "COOKIES_DIR": cookies,
        "RECENT": recent,
        "FOLDER_TEMPLATE_SHARED": folder_template,
        "DRY_RUN": dry_run,
        "CHOWN": chown,
    })
    if not cfg.apple_id:
        typer.echo("Debe proporcionar --apple-id/APPLE_ID via config/env.")
        raise typer.Exit(code=1)
    try:
        ensure_noninteractive_session(cfg.apple_id, cfg.cookies_dir)
    except AuthError as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)

    api = _get_api(cfg.apple_id, cfg.cookies_dir)
    photos = ICloudPhotos(api)
    state = StateDB(_make_state_path(cfg.cookies_dir))
    assets = photos.iter_normal_albums(cfg.recent, include=include, exclude=exclude)
    res = sync_assets(
        assets=assets,
        out_base=cfg.out_shared,
        folder_template=cfg.folder_template_shared,
        state=state,
        concurrency=cfg.concurrency,
        dry_run=cfg.dry_run,
        umask=cfg.umask,
        chown=cfg.chown,
    )
    logging.info(f"sync albums -> {res}")


@app.command(name="sync", help="Sincroniza todo: library y luego shared")
def sync_all(
    ctx: typer.Context,
    out: str = typer.Option("/data", "--out"),
    cookies: str = typer.Option("/cookies", "--cookies"),
    folder_template: str = typer.Option("{:%Y/%m}", "--folder-template"),
    shared_folder_template: str = typer.Option("{album}/{:%Y/%m}", "--shared-folder-template"),
    recent: Optional[int] = typer.Option(None, "--recent"),
    concurrency: int = typer.Option(4, "--concurrency"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    chown: Optional[str] = typer.Option(None, "--chown"),
):
    # Reutiliza los comandos anteriores
    ctx2 = ctx
    ctx2.obj = ctx.obj
    sync_library.callback = None  # satisfy type checker
    sync_shared.callback = None
    # library
    sync_library(
        ctx,
        out=out,
        cookies=cookies,
        recent=recent,
        concurrency=concurrency,
        folder_template=folder_template,
        dry_run=dry_run,
        chown=chown,
    )
    # shared dentro de /data/Compartidos
    shared_out = os.path.join(out, "Compartidos")
    sync_shared(
        ctx,
        out=shared_out,
        cookies=cookies,
        recent=recent,
        folder_template=shared_folder_template,
        include=None,
        exclude=None,
        dry_run=dry_run,
        chown=chown,
    )

    # álbumes no compartidos dentro de /data/Albums
    albums_out = os.path.join(out, "Albums")
    sync_albums(
        ctx,
        out=albums_out,
        cookies=cookies,
        recent=recent,
        folder_template=shared_folder_template,
        include=None,
        exclude=None,
        dry_run=dry_run,
        chown=chown,
    )


@app.command(help="Diagnóstico de entorno")
def doctor(
    apple_id: Optional[str] = typer.Option(None, "--apple-id", envvar="APPLE_ID"),
    cookies: str = typer.Option("/cookies", "--cookies"),
    out: str = typer.Option("/data", "--out"),
):
    setup_logging("INFO", None)
    ok = True
    if not apple_id:
        print("[WARN] APPLE_ID no configurado")
    if not os.path.isdir(cookies):
        print(f"[ERROR] No existe cookies dir: {cookies}")
        ok = False
    else:
        try:
            os.makedirs(os.path.join(cookies, ".icloudsync"), exist_ok=True)
            print(f"[OK] Cookies dir accesible: {cookies}")
        except Exception as e:
            print(f"[ERROR] Cookies dir no escribible: {e}")
            ok = False
    try:
        os.makedirs(out, exist_ok=True)
        test = os.path.join(out, ".w_test")
        with open(test, "w") as f:
            f.write("ok")
        os.remove(test)
        print(f"[OK] Ruta de salida accesible: {out}")
    except Exception as e:
        print(f"[ERROR] Ruta de salida no escribible: {e}")
        ok = False
    if ok:
        print("Diagnóstico OK. Ejecuta 'icloudsync auth' si faltan cookies.")
    raise typer.Exit(code=0 if ok else 2)


def main() -> None:  # console_script entry
    app()
