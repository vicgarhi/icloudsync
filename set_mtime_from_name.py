import os, re, sys, time, datetime
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/data")
# Prefijo tipo 20250801_060203_...
PAT = re.compile(r"(?P<date>\d{8})_(?P<time>\d{6})")

# Zona horaria local si quieres (Europe/Madrid). Si prefieres UTC, pon tz=None
try:
    import pytz
    tz = pytz.timezone("Europe/Madrid")
except Exception:
    tz = None

def parse_dt_from_name(name: str):
    m = PAT.search(name)
    if not m:
        return None
    d = m.group("date"); t = m.group("time")
    year, month, day = int(d[0:4]), int(d[4:6]), int(d[6:8])
    hh, mm, ss = int(t[0:2]), int(t[2:4]), int(t[4:6])
    dt = datetime.datetime(year, month, day, hh, mm, ss)
    if tz:
        dt = tz.localize(dt)
    return dt

changed = 0
scanned = 0
for root, _, files in os.walk(ROOT):
    for f in files:
        scanned += 1
        dt = parse_dt_from_name(f)
        if not dt:
            continue
        ts = dt.timestamp()
        path = os.path.join(root, f)
        try:
            os.utime(path, (ts, ts))
            changed += 1
        except Exception as e:
            print(f"ERROR ajustando {path}: {e}", file=sys.stderr)

print(f"Escaneados {scanned} ficheros; mtimes ajustados: {changed}")
