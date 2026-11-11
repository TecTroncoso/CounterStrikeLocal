#!/usr/bin/env bash
#
# Builds a clean dist/ and deploys it to Cloudflare Pages.
#
#   cp .env.example .env    # fill in the three values
#   bash scripts/deploy-cloudflare.sh
#
# Use --dry-run to build dist/ without uploading it.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        -h|--help)
            sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Opción desconocida: $arg" >&2
            exit 2
            ;;
    esac
done

if [[ -f .env ]]; then
    set -a
    # Strip Windows CRLF so values do not end with a stray \r.
    # shellcheck disable=SC1091
    source <(sed 's/\r$//' .env)
    set +a
fi

PARTS_BASE_URL="${PARTS_BASE_URL:-./valve-parts/}"
DIST="$ROOT/dist"

# Windows usually exposes Python as `python` (or `py -3`), not `python3`.
if command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1; then
    PYTHON=(python3)
elif command -v python >/dev/null 2>&1 && python -c "" >/dev/null 2>&1; then
    PYTHON=(python)
elif command -v py >/dev/null 2>&1 && py -3 -c "" >/dev/null 2>&1; then
    PYTHON=(py -3)
else
    echo "Falta Python 3 (python3, python o py -3)." >&2
    exit 1
fi

if [[ ! -f vendor/xash3d-fwgs/generated/xash.js || ! -d vendor/cs16-client/cstrike || ! -f vendor/jszip/jszip.min.js ]]; then
    echo "==> vendor/ incompleto; ejecutando scripts/fetch-vendor.py"
    "${PYTHON[@]}" scripts/fetch-vendor.py
fi

if [[ ! -f valve-parts/manifest.json ]]; then
    echo "Falta valve-parts/manifest.json. Ejecuta scripts/split-valve-parts.py." >&2
    exit 1
fi

echo "==> Verificando valve-parts/"
"${PYTHON[@]}" - <<'PY'
import json
import pathlib
import sys

root = pathlib.Path("valve-parts")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
parts = manifest.get("parts", [])
if not parts:
    sys.exit("manifest.json no contiene partes")

missing = [part["file"] for part in parts if not (root / part["file"]).is_file()]
wrong = [
    part["file"]
    for part in parts
    if (root / part["file"]).is_file()
    and (root / part["file"]).stat().st_size != part["size"]
]
if missing or wrong:
    print("Partes ausentes: " + (", ".join(missing) or "(ninguna)"), file=sys.stderr)
    print("Partes con tamaño incorrecto: " + (", ".join(wrong) or "(ninguna)"), file=sys.stderr)
    sys.exit(1)

print(f"  {len(parts)} partes, {manifest['archiveSize']} bytes")
PY

echo "==> Construyendo dist/ limpio"
rm -rf "$DIST"
mkdir -p "$DIST"
cp index.html loopback-net.js _headers "$DIST/"
if [[ -f favicon.ico ]]; then
    cp favicon.ico "$DIST/"
fi
cp -R vendor "$DIST/"
cp -R valve-parts "$DIST/"

# Generate the runtime config with the URL of the archive.  python3 writes
# valid JSON, so quotes or backslashes in the URL cannot break the script.
"${PYTHON[@]}" - "$PARTS_BASE_URL" "$DIST/config.js" <<'PY'
import json
import sys

url, target = sys.argv[1], sys.argv[2]
with open(target, "w", encoding="utf-8") as stream:
    stream.write("window.CS16_CONFIG = " + json.dumps({"partsBaseUrl": url}) + ";\n")
PY

echo "==> Contenido de dist/"
du -sh "$DIST"
ls -1 "$DIST" | sed 's/^/  /'

echo "==> Comprobando límites de Cloudflare Pages"
"${PYTHON[@]}" - "$DIST" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
files = [path for path in root.rglob("*") if path.is_file()]
limit = 25 * 1024 * 1024
too_big = [path for path in files if path.stat().st_size > limit]
if len(files) > 20000:
    sys.exit(f"Demasiados archivos: {len(files)} (máximo 20.000)")
if too_big:
    for path in too_big:
        print(f"  {path.relative_to(root)}: {path.stat().st_size} bytes", file=sys.stderr)
    sys.exit("Hay archivos de más de 25 MiB")
largest = max(files, key=lambda path: path.stat().st_size)
print(f"  {len(files)} archivos; el mayor: {largest.relative_to(root)} ({largest.stat().st_size} bytes)")
PY

if [[ "$DRY_RUN" == "1" ]]; then
    echo "==> Dry run: dist/ listo, no se despliega."
    exit 0
fi

: "${CLOUDFLARE_API_TOKEN:?Define CLOUDFLARE_API_TOKEN en .env}"
: "${CLOUDFLARE_ACCOUNT_ID:?Define CLOUDFLARE_ACCOUNT_ID en .env}"
: "${PAGES_PROJECT:?Define PAGES_PROJECT en .env}"

command -v node >/dev/null 2>&1 || {
    echo "Falta node (wrangler lo necesita)." >&2
    exit 1
}
command -v npx >/dev/null 2>&1 || {
    echo "Falta npx (wrangler lo necesita)." >&2
    exit 1
}

export CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID
export WRANGLER_SEND_METRICS=false

WRANGLER=(npx --yes wrangler@latest)

echo "==> Creando el proyecto si todavía no existe"
"${WRANGLER[@]}" pages project create "$PAGES_PROJECT" --production-branch main >/dev/null 2>&1 || true

echo "==> Subiendo dist/ a Cloudflare Pages"
"${WRANGLER[@]}" pages deploy "$DIST" --project-name "$PAGES_PROJECT" --branch main

echo
echo "Desplegado: https://${PAGES_PROJECT}.pages.dev"
if [[ "$PARTS_BASE_URL" != "./valve-parts/" ]]; then
    echo "Partes servidas desde: $PARTS_BASE_URL"
fi
