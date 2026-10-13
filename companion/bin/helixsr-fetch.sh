#!/usr/bin/env bash
# helixsr-fetch.sh - descarga HelixSR, lo compila en tu equipo y deja las dos DLL listas para usar.
#
#   ./helixsr-fetch.sh [--stable | --latest] [--out DIR] [--yes]
#
#   --stable        última versión estable (por defecto)
#   --latest        última versión publicada, sea estable o no (también vale --lastest)
#   --out DIR       carpeta de destino (se crea si hace falta); por defecto, la carpeta actual
#   --yes, -y       no pide confirmación (acepta la descarga de la DLL de DLSS de NVIDIA)
#
# Deja en el destino:
#   amd_fidelityfx_dx12.dll
#   amd_fidelityfx_upscaler_dx12.dll
# (HelixSR con la red incrustada: es la misma DLL con los dos nombres de FSR 3.1.)
#
# Todo lo demás (zip, Python portable, compilador de shaders, prefijo de Wine) va a un directorio
# temporal que se borra al terminar. El script oficial de HelixSR se ejecuta sin modificar.
# Necesita: bash, curl, unzip, Python 3 con numpy (o el setup descarga uno portable) y Proton/Wine.
#
# AVISO: la red procede de la DLL de DLSS de NVIDIA (su licencia). Las DLL generadas son para tu
# propio equipo: no las compartas ni las subas a ningún sitio.
set -euo pipefail

REPO="lonewolf0622/HelixSR"
CHANNEL=stable
OUT="$PWD"
ASSUME_YES=0
DLSS_LICENSE="https://github.com/NVIDIA/DLSS/blob/v310.7.0/LICENSE.txt"

say() { printf '[helixsr-fetch] %s\n' "$*"; }
die() { printf '[helixsr-fetch] error: %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; }

# --- argumentos ---
while [ $# -gt 0 ]; do
    case "$1" in
        --stable) CHANNEL=stable ;;
        --latest|--lastest) CHANNEL=latest ;;
        --out) [ $# -ge 2 ] || die "--out necesita una carpeta"; OUT="$2"; shift ;;
        --out=*) OUT="${1#--out=}" ;;
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
mkdir -p "$T/pkg" "$T/data"
unzip -q "$T/helixsr.zip" -d "$T/pkg" || die "no se pudo descomprimir el zip"
SETUP=$(find "$T/pkg" -name helixsr-setup.sh | head -n1)
[ -n "$SETUP" ] || die "este release no trae helixsr-setup.sh"
PKG=$(dirname "$SETUP")

# --- compilar con el setup oficial, sin modificarlo ---
# --yes acepta sus descargas (ya consentidas arriba). La entrada vacía hace que su pregunta final por cada
# juego reciba EOF y no instale nada en ninguno. XDG_DATA_HOME lleva Python/DXC al temporal.
say "compilando HelixSR (puede tardar unos minutos)..."
LOG="$T/build.log"
set +e
( cd "$PKG" && XDG_DATA_HOME="$T/data" bash ./helixsr-setup.sh --yes </dev/null ) 2>&1 \
    | tee "$LOG" | sed -u '/looking for games/,$d'
set -e

# --- comprobar y copiar ---
has_net() { [ -s "$1" ] && [ "$(tail -c 32 "$1" | head -c 8 | tr -d '\0')" = HXSRNET1 ]; }
SRC_A="$PKG/fsr3-drop-in/amd_fidelityfx_dx12.dll"
SRC_B="$PKG/fsr3-drop-in/amd_fidelityfx_upscaler_dx12.dll"
if ! has_net "$SRC_A" || ! has_net "$SRC_B"; then
    # versiones sin fsr3-drop-in: la DLL de la raíz es la misma, con los dos nombres
    if has_net "$PKG/amd_fidelityfx_dx12.dll"; then
        SRC_A="$PKG/amd_fidelityfx_dx12.dll"; SRC_B="$PKG/amd_fidelityfx_dx12.dll"
    else
        cp "$LOG" "$PWD/helixsr-fetch-error.log" 2>/dev/null || true
        die "la compilación no generó las DLL con la red (log en $PWD/helixsr-fetch-error.log)"
    fi
fi
VER=$(head -c 4194304 "$SRC_A" | grep -a -o 'HelixSR [0-9]\+\.[0-9]\+\.[0-9]\+' | head -n1 | cut -d' ' -f2 || true)

mkdir -p "$OUT" || die "no se pudo crear $OUT"
cp -f "$SRC_A" "$OUT/amd_fidelityfx_dx12.dll"
cp -f "$SRC_B" "$OUT/amd_fidelityfx_upscaler_dx12.dll"
say "listo: HelixSR ${VER:-$TAG} en $OUT"
ls -l "$OUT/amd_fidelityfx_dx12.dll" "$OUT/amd_fidelityfx_upscaler_dx12.dll"
