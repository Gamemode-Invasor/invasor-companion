#!/usr/bin/env bash
# helixsr-fetch.sh - descarga HelixSR, lo compila en tu equipo y deja una DLL y su ini listos para usar.
#
#   ./helixsr-fetch.sh [--stable | --latest] [--out DIR] [--force] [--yes]
#
#   --stable        última versión estable (por defecto)
#   --latest        última versión publicada, sea estable o no (también vale --lastest)
#   --out DIR       carpeta de destino (se crea si hace falta); por defecto ~/.local/share/HelixSR
#   --force         recompila aunque la versión instalada ya sea la última
#   --yes, -y       no pide confirmación (acepta la descarga de la DLL de DLSS de NVIDIA)
#
# Deja en el destino (como la carpeta fsr-dropin de HelixSR, con la DLL renombrada):
#   helixsr.dll     HelixSR con la red incrustada
#   helixsr.ini     ajustes; al actualizar se conservan tus valores y se añaden las opciones nuevas
#   .version        etiqueta de la versión instalada
# Todo se construye y se valida en un temporal antes de tocar el destino: si algo falla, lo que hubiera
# en el destino queda como estaba. El temporal (zip, Python portable, compilador de shaders, prefijo de
# Wine) se borra siempre. El script oficial de HelixSR se ejecuta sin modificar.
# Necesita: bash, curl, unzip, Python 3 con numpy (o el setup descarga uno portable) y Proton/Wine.
#
# AVISO: la red procede de la DLL de DLSS de NVIDIA (su licencia). Las DLL generadas son para tu
# propio equipo: no las compartas ni las subas a ningún sitio.
set -euo pipefail

REPO="lonewolf0622/HelixSR"
CHANNEL=stable
OUT="${XDG_DATA_HOME:-$HOME/.local/share}/HelixSR"
FORCE=0
ASSUME_YES=0
DLSS_LICENSE="https://github.com/NVIDIA/DLSS/blob/v310.7.0/LICENSE.txt"
DLL_NAME="helixsr.dll"
INI_NAME="helixsr.ini"

say() { printf '[helixsr-fetch] %s\n' "$*"; }
die() { printf '[helixsr-fetch] error: %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; }

# --- argumentos ---
while [ $# -gt 0 ]; do
    case "$1" in
        --stable) CHANNEL=stable ;;
        --latest|--lastest) CHANNEL=latest ;;
        --out) [ $# -ge 2 ] || die "--out necesita una carpeta"; OUT="$2"; shift ;;
        --out=*) OUT="${1#--out=}" ;;
        --force) FORCE=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "opción desconocida: $1 (prueba --help)" ;;
    esac
    shift
done
[ -n "$OUT" ] || die "--out no puede estar vacío"
[ "$(uname -m)" = x86_64 ] || die "solo x86-64 Linux"
for t in curl unzip; do
    command -v "$t" >/dev/null || die "falta la herramienta: $t"
done

# --- qué versión ---
if [ "$CHANNEL" = stable ]; then
    API="https://api.github.com/repos/$REPO/releases/latest"
else
    API="https://api.github.com/repos/$REPO/releases?per_page=1"
fi
say "buscando la última versión ($CHANNEL)..."
JSON=$(curl -fsSL -H 'Accept: application/vnd.github+json' "$API") || die "no se pudo consultar $API"
TAG=$(printf '%s' "$JSON" | grep -o '"tag_name": *"[^"]*"' | head -n1 | sed 's/.*: *"\(.*\)"/\1/')
URL=$(printf '%s' "$JSON" | grep -o '"browser_download_url": *"[^"]*\.zip"' | head -n1 | sed 's/.*: *"\(.*\)"/\1/')
[ -n "$TAG" ] && [ -n "$URL" ] || die "no encuentro un release con zip en $API"
say "versión: $TAG"

if [ "$FORCE" != 1 ] && [ -s "$OUT/$DLL_NAME" ] && [ "$(cat "$OUT/.version" 2>/dev/null || true)" = "$TAG" ]; then
    say "al día: HelixSR $TAG ya está en $OUT"
    exit 0
fi

# --- confirmación (la DLL de NVIDIA se descarga y se usa una vez) ---
if [ "$ASSUME_YES" != 1 ]; then
    [ -t 0 ] || die "sin terminal interactiva: usa --yes para aceptar la descarga de la DLL de NVIDIA"
    cat <<EOF
Se va a descargar HelixSR $TAG y, para compilarlo, la DLL de DLSS 310.7.0 de NVIDIA (se usa una vez y
se borra). Su licencia: $DLSS_LICENSE
Las DLL resultantes llevan la red de NVIDIA: son solo para tu equipo, no las compartas.
Destino: $OUT
EOF
    read -r -p "¿Continuar? [S/n] " ans || ans=n
    case "$ans" in ''|s|S|y|Y|si|SI|yes|YES) ;; *) die "cancelado" ;; esac
fi

# --- temporal (se borra siempre) ---
T=$(mktemp -d) || die "no se pudo crear el directorio temporal"
cleanup() { rm -rf "$T"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

say "descargando..."
curl -fL --retry 3 -sS -o "$T/helixsr.zip" "$URL" || die "falló la descarga: $URL"
mkdir -p "$T/pkg" "$T/data" "$T/cache" "$T/config"
unzip -q "$T/helixsr.zip" -d "$T/pkg" || die "no se pudo descomprimir el zip"
SETUP=$(find "$T/pkg" -name helixsr-setup.sh | head -n1)
[ -n "$SETUP" ] || die "este release no trae helixsr-setup.sh"
PKG=$(dirname "$SETUP")

# --- compilar con el setup oficial, sin modificarlo ---
# --yes acepta sus descargas (ya consentidas arriba). La entrada vacía hace que su pregunta final por cada
# juego reciba EOF y no instale nada en ninguno. Los XDG_* llevan Python/DXC/prefijo y cachés al temporal
# (HOME no se toca: Proton se busca en ~/.local/share/Steam).
say "compilando HelixSR (puede tardar unos minutos)..."
LOG="$T/build.log"
set +e
( cd "$PKG" && XDG_DATA_HOME="$T/data" XDG_CACHE_HOME="$T/cache" XDG_CONFIG_HOME="$T/config" \
    bash ./helixsr-setup.sh --yes </dev/null ) 2>&1 \
    | tee "$LOG" | sed -u '/looking for games/,$d'
set -e

# --- localizar el resultado (tolerante a cambios de carpetas del autor) ---
# La DLL buscada: .dll de más de 1 MB con la red incrustada (marcador HXSRNET1 al final).
has_net() { [ -f "$1" ] && [ "$(wc -c <"$1")" -gt 1048576 ] && [ "$(tail -c 32 "$1" | head -c 8 | tr -d '\0')" = HXSRNET1 ]; }
fail() {
    printf '[helixsr-fetch] ---- últimas líneas de la compilación ----\n' >&2
    tail -n 30 "$LOG" >&2 || true
    die "$1"
}

SRC_DLL=""; SRC_DIR=""
CANDIDATES=()
while IFS= read -r d; do CANDIDATES+=("$d"); done < <(find "$T/pkg" -type d -name fsr-dropin 2>/dev/null)
CANDIDATES+=("$PKG/fsr3-drop-in" "$PKG")
for d in "${CANDIDATES[@]}"; do
    [ -d "$d" ] || continue
    for f in "$d/amd_fidelityfx_dx12.dll" "$d/amd_fidelityfx_upscaler_dx12.dll" "$d"/*.dll; do
        if has_net "$f"; then SRC_DLL="$f"; SRC_DIR="$d"; break 2; fi
    done
done
[ -n "$SRC_DLL" ] || fail "la compilación no generó una DLL con la red incrustada (¿cambió el formato de HelixSR?)"

SRC_INI="$SRC_DIR/$INI_NAME"
[ -f "$SRC_INI" ] || SRC_INI=$(find "$T/pkg" -name "$INI_NAME" 2>/dev/null | head -n1)

VER=$(head -c 4194304 "$SRC_DLL" | grep -a -o 'HelixSR [0-9]\+\.[0-9]\+\.[0-9]\+' | head -n1 | cut -d' ' -f2 || true)

# --- instalar: cada fichero con rename atómico, y la versión al final ---
mkdir -p "$OUT" || die "no se pudo crear $OUT"
cp -f "$SRC_DLL" "$OUT/$DLL_NAME.new" && mv -f "$OUT/$DLL_NAME.new" "$OUT/$DLL_NAME" \
    || { rm -f "$OUT/$DLL_NAME.new"; die "no se pudo instalar $DLL_NAME en $OUT"; }
if [ -f "$OUT/$INI_NAME" ] && [ -n "$SRC_INI" ] && [ -f "$SRC_INI" ]; then
    # El ini nuevo manda en estructura y comentarios; tus valores se conservan. Las opciones que
    # el ini nuevo añade quedan con su valor por defecto; las que ya no existen se descartan.
    awk -v added="$T/ini.added" '
        function trim(x) { gsub(/\r$/, "", x); sub(/^[ \t]+/, "", x); sub(/[ \t]+$/, "", x); return x }
        FNR == NR {
            line = trim($0)
            if (line ~ /^\[.*\]$/) { sec = tolower(line); next }
            if (line ~ /^[;#]/ || index(line, "=") == 0) next
            k = trim(substr(line, 1, index(line, "=") - 1)); v = trim(substr(line, index(line, "=") + 1))
            mine[sec SUBSEP tolower(k)] = v
            next
        }
        {
            line = trim($0); cr = ($0 ~ /\r$/) ? "\r" : ""
            if (line ~ /^\[.*\]$/) { sec = tolower(line); print; next }
            if (line !~ /^[;#]/ && index(line, "=") > 0) {
                k = trim(substr(line, 1, index(line, "=") - 1))
                key = sec SUBSEP tolower(k)
                if (key in mine) { print k " = " mine[key] cr; next }
                print k " (nueva)" > added
            }
            print
        }' "$OUT/$INI_NAME" "$SRC_INI" >"$T/ini.merged"
    if [ -s "$T/ini.merged" ] && ! cmp -s "$T/ini.merged" "$OUT/$INI_NAME"; then
        cp -f "$T/ini.merged" "$OUT/$INI_NAME.new" && mv -f "$OUT/$INI_NAME.new" "$OUT/$INI_NAME" \
            || { rm -f "$OUT/$INI_NAME.new"; die "no se pudo actualizar $INI_NAME en $OUT"; }
        say "$INI_NAME actualizado: se conservan tus valores"
    fi
    if [ -s "$T/ini.added" ]; then
        say "opciones nuevas en $INI_NAME: $(paste -sd, "$T/ini.added")"
    fi
elif [ -f "$OUT/$INI_NAME" ]; then
    say "se conserva tu $INI_NAME"
elif [ -n "$SRC_INI" ] && [ -f "$SRC_INI" ]; then
    cp -f "$SRC_INI" "$OUT/$INI_NAME.new" && mv -f "$OUT/$INI_NAME.new" "$OUT/$INI_NAME" \
        || { rm -f "$OUT/$INI_NAME.new"; die "no se pudo instalar $INI_NAME en $OUT"; }
else
    say "aviso: este release no trae $INI_NAME; HelixSR usará sus valores por defecto"
fi
printf '%s\n' "$TAG" >"$OUT/.version.new" && mv -f "$OUT/.version.new" "$OUT/.version" \
    || { rm -f "$OUT/.version.new"; die "no se pudo escribir la versión en $OUT"; }

# la carpeta de versiones anteriores del módulo (ya no se usa)
rm -rf "$HOME/.local/share/invasor/user-modules/companion/HelixSR" 2>/dev/null || true

say "listo: HelixSR ${VER:-$TAG} en $OUT"
ls -l "$OUT"
