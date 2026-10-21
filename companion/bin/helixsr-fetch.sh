#!/usr/bin/env bash
# helixsr-fetch.sh - descarga HelixSR, lo compila en tu equipo y deja HelixSR Scaler (el OptiScaler de
# HelixSR) con la DLL, listo para copiar al C:\windows\system32\umu de un juego.
#
#   ./helixsr-fetch.sh [--stable | --latest] [--out DIR] [--force] [--yes]
#
#   --stable        última versión estable (por defecto)
#   --latest        última versión publicada, sea estable o no (también vale --lastest)
#   --out DIR       carpeta de destino (se crea si hace falta); por defecto ~/.local/share/HelixSR
#   --force         recompila aunque la versión instalada ya sea la última
#   --yes, -y       no pide confirmación (acepta la descarga de la DLL de DLSS de NVIDIA)
#
# Deja en el destino (lo que va al umu del juego, que se lanza con WINE_OPTISCALER_NAME=dxgi.dll):
#   helixsr.dll         HelixSR con la red incrustada
#   helixsr.ini         ajustes de HelixSR
#   OptiScaler.dll      HelixSR Scaler, con OptiScaler/ (sus DLL de AMD y XeSS), Licenses/ y sus README
#   OptiScaler/nvngx_dlss*.dll   las DLL de DLSS 310.7.0 de NVIDIA: HelixSR Scaler las busca junto a su DLL para
#                       que el juego vea DLSS (sin ellas apaga el spoofing); se descargan si faltan
#   OptiScaler.ini      el del release, ajustado para umu (HelixSR en FfxDx12SRPath)
#   .version            etiqueta de la versión instalada
# Al actualizar, los dos ini conservan tus valores y reciben las opciones nuevas.
# Todo se construye y se valida en un temporal antes de tocar el destino: si algo falla, lo que hubiera
# en el destino queda como estaba. El temporal (zip, Python portable, compilador de shaders, prefijo de
# Wine) y la carpeta .staging del destino se borran siempre. helixsr-setup.sh corre sin modificar y su
# paso de juegos se anula en el temporal: no se instala nada en ningún juego.
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
NVNGX_URL="https://github.com/NVIDIA/DLSS/raw/v310.7.0/lib/Windows_x86_64/rel"
NVNGX_FILES=(nvngx_dlss.dll nvngx_dlssd.dll nvngx_dlssg.dll)
DLL_NAME="helixsr.dll"
INI_NAME="helixsr.ini"
OPTI_DLL="OptiScaler.dll"
OPTI_INI="OptiScaler.ini"
STAGING=""

say() { printf '[helixsr-fetch] %s\n' "$*"; }
die() { printf '[helixsr-fetch] error: %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'; }

# ensure_nvngx CARPETA: deja en CARPETA (la OptiScaler/ de un destino o de su temporal) las nvngx_dlss*.dll que
# falten: primero las que ya hay en $OUT/OptiScaler y, si no, las descarga de NVIDIA. Si no se puede, avisa y
# sigue: HelixSR se instala igual, solo que el juego no verá DLSS.
ensure_nvngx() {
    local dir=$1 f tmp
    mkdir -p "$dir" || return 0
    for f in "${NVNGX_FILES[@]}"; do
        [ -s "$dir/$f" ] && continue
        if [ -s "$OUT/OptiScaler/$f" ]; then
            cp -f "$OUT/OptiScaler/$f" "$dir/$f" && continue
        fi
        tmp=$(mktemp "$dir/.$f.XXXXXX") || { say "aviso: no pude preparar $f"; continue; }
        if curl -fL --retry 3 -sS -o "$tmp" "$NVNGX_URL/$f" && [ -s "$tmp" ]; then
            chmod 644 "$tmp" && mv -f "$tmp" "$dir/$f"
        else
            rm -f "$tmp"
            say "aviso: no pude descargar $f de NVIDIA: el juego no verá DLSS hasta que esté en $dir"
        fi
    done
    return 0
}
nvngx_missing() {
    local f
    for f in "${NVNGX_FILES[@]}"; do [ -s "$OUT/OptiScaler/$f" ] || return 0; done
    return 1
}

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

if [ "$FORCE" != 1 ] && [ -s "$OUT/$DLL_NAME" ] && [ -s "$OUT/$OPTI_DLL" ] && [ "$(cat "$OUT/.version" 2>/dev/null || true)" = "$TAG" ]; then
    say "al día: HelixSR $TAG ya está en $OUT"
    if nvngx_missing && { [ "$ASSUME_YES" = 1 ] || [ -t 0 ]; }; then
        if [ "$ASSUME_YES" != 1 ]; then
            read -r -p "Faltan las DLL de DLSS 310.7.0 de NVIDIA (licencia: $DLSS_LICENSE). ¿Descargarlas? [S/n] " ans || ans=n
            case "$ans" in ''|s|S|y|Y|si|SI|yes|YES) ;; *) exit 0 ;; esac
        fi
        say "descargando las DLL de DLSS de NVIDIA a $OUT/OptiScaler..."
        ensure_nvngx "$OUT/OptiScaler"
    fi
    exit 0
fi

# --- confirmación (las DLL de NVIDIA se descargan) ---
if [ "$ASSUME_YES" != 1 ]; then
    [ -t 0 ] || die "sin terminal interactiva: usa --yes para aceptar la descarga de la DLL de NVIDIA"
    cat <<EOF
Se va a descargar HelixSR $TAG y, para compilarlo, la DLL de DLSS 310.7.0 de NVIDIA (se usa una vez y
se borra). Además se guardan en OptiScaler/ las DLL de DLSS 310.7.0 que HelixSR Scaler necesita para que
el juego vea DLSS (nvngx_dlss, nvngx_dlssd y nvngx_dlssg). Su licencia: $DLSS_LICENSE
Las DLL resultantes llevan la red de NVIDIA: son solo para tu equipo, no las compartas.
Destino: $OUT
EOF
    read -r -p "¿Continuar? [S/n] " ans || ans=n
    case "$ans" in ''|s|S|y|Y|si|SI|yes|YES) ;; *) die "cancelado" ;; esac
fi

# --- temporal (se borra siempre) ---
T=$(mktemp -d) || die "no se pudo crear el directorio temporal"
cleanup() { rm -rf "$T"; [ -z "$STAGING" ] || rm -rf "$STAGING"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

say "descargando..."
curl -fL --retry 3 -sS -o "$T/helixsr.zip" "$URL" || die "falló la descarga: $URL"
mkdir -p "$T/pkg" "$T/data" "$T/cache" "$T/config"
unzip -q "$T/helixsr.zip" -d "$T/pkg" || die "no se pudo descomprimir el zip"
SETUP=$(find "$T/pkg" -name helixsr-setup.sh | head -n1)
[ -n "$SETUP" ] || die "este release no trae helixsr-setup.sh"
PKG=$(dirname "$SETUP")

# --- aislamiento del paso de juegos: aquí solo se genera la DLL ---
# HelixSR v2.0.0 (2026-10-19) hace que helixsr-setup.sh reenvíe --yes a su paso de juegos
# (setup/helixsr_install.py): con eso instala HelixSR en TODOS los juegos que encuentre (en
# v1.9.3 --yes no llegaba allí y el EOF de </dev/null detenía el paso sin tocar nada).
# Doble barrera; si no se puede montar ninguna, el script muere sin llegar al setup:
#   A) setup/helixsr_install.py del zip temporal -> no-op (el paso de juegos ni se ejecuta);
#   B) HOME temporal sin bibliotecas de Steam (el escaneo usa Path.home()): el escaneo no ve
#      ningún juego; solo se enlaza ahí la herramienta de Proton/Wine real, que el build
#      necesita para el compilador de shaders (compatibilitytools.d no es biblioteca).
A_OK=0
B_OK=0
SETUP_HOME="$HOME"
INSTALLER="$PKG/setup/helixsr_install.py"
if [ -f "$INSTALLER" ]; then
    cat > "$INSTALLER" <<'PY'
#!/usr/bin/env python3
import sys
print("[helixsr-setup] games step skipped (helixsr-fetch: only the DLL is built)", flush=True)
sys.exit(0)
PY
    A_OK=1
    say "paso de juegos anulado (esta descarga solo genera la DLL)"
else
    say "aviso: este release no trae setup/helixsr_install.py (¿cambió HelixSR?): hace falta el HOME temporal"
fi
for p in "$HOME"/.local/share/Steam/steamapps/common/Proton*/files/bin/wine \
         "$HOME"/.steam/steam/steamapps/common/Proton*/files/bin/wine \
         "$HOME"/.local/share/Steam/compatibilitytools.d/*/files/bin/wine \
         "$HOME"/.steam/root/compatibilitytools.d/*/files/bin/wine; do
    if [ -x "$p" ]; then
        TOOL=${p%/files/bin/wine}
        mkdir -p "$T/home/.local/share/Steam/compatibilitytools.d"
        ln -sfn "$TOOL" "$T/home/.local/share/Steam/compatibilitytools.d/$(basename "$TOOL")"
        SETUP_HOME="$T/home"
        B_OK=1
        say "HOME temporal para el setup (juegos invisibles; Proton/Wine enlazado: $(basename "$TOOL"))"
        break
    fi
done
if [ "$B_OK" = 0 ]; then
    say "aviso: no encontré Proton/Wine para el HOME temporal: el setup corre con el HOME real"
fi
if [ "$A_OK" = 0 ] && [ "$B_OK" = 0 ]; then
    die "no se puede anular ni aislar el paso de juegos: revisa helixsr-fetch.sh contra este release"
fi

# --- compilar con el setup oficial ---
# --yes acepta sus descargas (ya consentidas arriba); desde HelixSR v2.0.0 reenvía además --yes
# al paso de juegos, que así instalaría en todos (por eso el no-op de setup/helixsr_install.py
# y el HOME temporal del bloque anterior). Los XDG_* llevan Python/DXC/prefijo y cachés al
# temporal; el HOME es el temporal cuando hubo herramienta que enlazar, y si no el real (sigue
# protegido el no-op).
say "compilando HelixSR (puede tardar unos minutos)..."
LOG="$T/build.log"
set +e
( cd "$PKG" && HOME="$SETUP_HOME" XDG_DATA_HOME="$T/data" XDG_CACHE_HOME="$T/cache" XDG_CONFIG_HOME="$T/config" \
    bash ./helixsr-setup.sh --yes </dev/null ) 2>&1 \
    | tee "$LOG"
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

# --- HelixSR Scaler (el OptiScaler de HelixSR, en el mismo zip) ---
SCALER=""
while IFS= read -r d; do
    if [ -f "$d/$OPTI_DLL" ] && [ -f "$d/$OPTI_INI" ] && [ -d "$d/OptiScaler" ]; then SCALER="$d"; break; fi
done < <(find "$T/pkg" -type d -name helixsr-scaler 2>/dev/null)
[ -n "$SCALER" ] || fail "este release no trae helixsr-scaler con $OPTI_DLL, $OPTI_INI y OptiScaler/ (¿cambió HelixSR?)"

# set_ini FICHERO "Sección|Clave|valor"...: cambia el valor de cada clave dentro de su sección (conserva
# comentarios, espacios y CRLF); si alguna no aparece, falla sin tocar el fichero. Los valores van por el
# entorno, no por -v: awk interpretaría las barras de c:\windows.
set_ini() {
    local file=$1; shift
    SETS=$(printf '%s\n' "$@") awk '
        function trim(x) { gsub(/\r$/, "", x); sub(/^[ \t]+/, "", x); sub(/[ \t]+$/, "", x); return x }
        BEGIN {
            n = split(ENVIRON["SETS"], s, "\n")
            for (i = 1; i <= n; i++) {
                if (s[i] == "") continue
                split(s[i], p, "|"); key = tolower("[" p[1] "]") SUBSEP tolower(p[2])
                want[key] = p[3]; name[key] = p[1] "." p[2]
            }
        }
        {
            line = trim($0); cr = ($0 ~ /\r$/) ? "\r" : ""
            if (line ~ /^\[.*\]$/) { sec = tolower(line); print; next }
            if (line !~ /^[;#]/ && index(line, "=") > 0) {
                key = sec SUBSEP tolower(trim(substr(line, 1, index(line, "=") - 1)))
                if (key in want) {
                    eq = index($0, "="); rest = substr($0, eq + 1); match(rest, /^[ \t]*/)
                    print substr($0, 1, eq) substr(rest, 1, RLENGTH) want[key] cr
                    done[key] = 1; next
                }
            }
            print
        }
        END { bad = 0; for (k in want) if (!(k in done)) { print "falta " name[k] > "/dev/stderr"; bad = 1 }; exit bad }
    ' "$file" >"$file.set" && mv -f "$file.set" "$file" || { rm -f "$file.set"; return 1; }
}

# merge_ini TUYO NUEVO AÑADIDAS: el ini nuevo con tus valores. Manda su estructura y sus comentarios; las
# opciones que ya no existen se descartan y las nuevas (anotadas en AÑADIDAS) quedan con su valor por
# defecto. Solo cambia las líneas cuyo valor difiere, con el mismo formato que la línea del ini nuevo.
merge_ini() {
    awk -v added="$3" '
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
                if (key in mine) {
                    if (mine[key] != trim(substr(line, index(line, "=") + 1))) {
                        eq = index($0, "="); rest = substr($0, eq + 1); match(rest, /^[ \t]*/)
                        print substr($0, 1, eq) substr(rest, 1, RLENGTH) mine[key] cr; next
                    }
                } else {
                    print k " (nueva)" > added
                }
            }
            print
        }' "$1" "$2"
}

# --- montar el resultado en el temporal (como el umu de un juego que funciona) ---
OUT_DIR="$T/out"
mkdir -p "$OUT_DIR"
cp -f "$SRC_DLL" "$OUT_DIR/$DLL_NAME" || die "no se pudo preparar $DLL_NAME"
if [ -n "$SRC_INI" ] && [ -f "$SRC_INI" ]; then
    cp -f "$SRC_INI" "$OUT_DIR/$INI_NAME" || die "no se pudo preparar $INI_NAME"
else
    say "aviso: este release no trae $INI_NAME; HelixSR usará sus valores por defecto"
fi
for f in "$OPTI_DLL" "$OPTI_INI" README.txt README-Linux.txt; do
    [ -f "$SCALER/$f" ] && { cp -f "$SCALER/$f" "$OUT_DIR/" || die "no se pudo preparar $f"; }
done
for d in OptiScaler Licenses; do
    [ -d "$SCALER/$d" ] && { cp -R "$SCALER/$d" "$OUT_DIR/" || die "no se pudo preparar $d/"; }
done
# Las DLL de DLSS no vienen en el release: las que ya había en el destino o, si no, las de NVIDIA.
ensure_nvngx "$OUT_DIR/OptiScaler"
# OptiScaler.ini: el del release con los valores que hacen falta para cargarlo desde
# C:\windows\system32\umu con WINE_OPTISCALER_NAME (HelixSR solo en FfxDx12SRPath: en los dos huecos
# se llama a sí mismo sin fin).
set_ini "$OUT_DIR/$OPTI_INI" \
    'Upscalers|Dx12Upscaler|ffx' \
    'Libraries|OptiDllPath|c:\windows\system32\umu\OptiScaler' \
    'Libraries|FfxDx12SRPath|C:\Windows\System32\umu\helixsr.dll' \
    'Hotfix|CheckForUpdate|false' \
    || fail "el $OPTI_INI de este release no tiene las opciones esperadas (¿cambió HelixSR Scaler?)"

# Tus ini: se conservan tus valores y se añaden las opciones nuevas.
for ini in "$INI_NAME" "$OPTI_INI"; do
    [ -f "$OUT/$ini" ] || continue
    if [ ! -f "$OUT_DIR/$ini" ]; then
        cp -f "$OUT/$ini" "$OUT_DIR/$ini" || die "no se pudo preparar $ini"
        say "se conserva tu $ini"
        continue
    fi
    : >"$T/ini.added"
    merge_ini "$OUT/$ini" "$OUT_DIR/$ini" "$T/ini.added" >"$T/ini.merged" || die "no se pudo fusionar $ini"
    [ -s "$T/ini.merged" ] || die "la fusión de $ini salió vacía"
    mv -f "$T/ini.merged" "$OUT_DIR/$ini"
    if [ -s "$T/ini.added" ]; then
        say "opciones nuevas en $ini: $(paste -sd, "$T/ini.added")"
    else
        say "$ini: se conservan tus valores"
    fi
done

# --- instalar ---
# Primero todo a $OUT/.staging (mismo disco: los mv son renombres); luego cada elemento se cambia por
# rename y la versión va al final. Sin .version durante el cambio, un corte se recompila en la siguiente
# ejecución. La carpeta .staging se borra siempre (trap), con lo viejo que hubiera dentro.
mkdir -p "$OUT" || die "no se pudo crear $OUT"
STAGING="$OUT/.staging"
rm -rf "$STAGING"
mkdir "$STAGING" && cp -R "$OUT_DIR/." "$STAGING/" || die "no se pudo copiar a $OUT"
rm -f "$OUT/.version"
for item in "$DLL_NAME" "$INI_NAME" "$OPTI_DLL" "$OPTI_INI" OptiScaler Licenses README.txt README-Linux.txt; do
    [ -e "$STAGING/$item" ] || continue
    if [ -d "$STAGING/$item" ] && [ -e "$OUT/$item" ]; then
        mv -f "$OUT/$item" "$STAGING/$item.old" || die "no se pudo reemplazar $item en $OUT"
        mv -f "$STAGING/$item" "$OUT/$item" \
            || { mv -f "$STAGING/$item.old" "$OUT/$item"; die "no se pudo instalar $item en $OUT"; }
    else
        mv -f "$STAGING/$item" "$OUT/$item" || die "no se pudo instalar $item en $OUT"
    fi
done
printf '%s\n' "$TAG" >"$STAGING/.version" && mv -f "$STAGING/.version" "$OUT/.version" \
    || die "no se pudo escribir la versión en $OUT"

# la carpeta de versiones anteriores del módulo (ya no se usa)
rm -rf "$HOME/.local/share/invasor/user-modules/companion/HelixSR" 2>/dev/null || true

say "listo: HelixSR ${VER:-$TAG} con HelixSR Scaler en $OUT"
ls -l "$OUT"
