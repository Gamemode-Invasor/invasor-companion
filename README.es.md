# Companion

[English](README.md) · **Español**

Un módulo para [Invasor](../invasor) que **construye las opciones de lanzamiento de Steam de un juego** (`VAR=valor … mangohud mako-launch %command%`)
desde el panel, con el mando, y las copia al portapapeles. Pega el resultado en Propiedades › General ›
Opciones de lanzamiento del juego. Añade una pestaña **Compa** (que no aparece en el Acceso rápido) con cuatro páginas:

- **Lanzador**: una vista previa en vivo del comando y un botón *Copiar* arriba, y después las opciones en secciones:
  FG/escaladores (MAKO, lsfg-vk, FSR 4, HelixSR), MangoHud (límite de FPS, API y FPS), gráficos (wined3d, Zink, HDR, Direct3D),
  Proton (compatibilidad de 32 bits, large address aware, esync/fsync, PROTON LOG = `PROTON_LOG=1` al principio de todo el comando, para que Proton deje `~/steam-<AppID>.log`, prefijo elegido en un explorador de carpetas que empieza en `compatdata` y puede ir a cualquier sitio), entorno (DLL overrides, «no es una Steam Deck» = `SteamDeck=0`, variables personalizadas)
  y *Restablecer todo*. Las combinaciones incompatibles o vacías muestran un aviso. Las elecciones no se guardan: se restablecen al recargar la pestaña.
  MAKO y lsfg-vk se excluyen entre sí, y también FSR 4 y HelixSR: al activar uno se desactiva el otro.
  HelixSR necesita su DLL: *Descargar y generar DLL* baja el release y la compila con el setup oficial en una carpeta temporal (la UI pide confirmar la licencia de DLSS); su paso de juegos no se ejecuta, así que **no se instala nada en ningún juego** (la instalación por juego sigue siendo solo *Copiar HelixSR al juego*). El resultado queda en `~/.local/share/HelixSR/`: HelixSR Scaler, el OptiScaler que trae el release (`OptiScaler.dll`, `OptiScaler.ini`, `OptiScaler/`, `Licenses/` y sus README), con `helixsr.dll`, `helixsr.ini` y un fichero `.version`. `OptiScaler/` lleva además las `nvngx_dlss.dll`, `nvngx_dlssd.dll` y `nvngx_dlssg.dll` de DLSS 310.7.0 de NVIDIA (se descargan si faltan y se conservan, solo para tu equipo): HelixSR Scaler busca `nvngx_dlss.dll` junto a su DLL y, sin ella, apaga el spoofing y el juego nunca ofrece DLSS. Si un juego tiene la versión actual pero le faltan, se le vuelve a proponer la copia. El `OptiScaler.ini` sale ajustado para cargarse desde `C:\windows\system32\umu`, con HelixSR solo en `FfxDx12SRPath`, y `Dx11Upscaler=ffx_12`, `Dx12Upscaler=ffx` y `VulkanUpscaler=ffx_12` para que todas las APIs pasen por HelixSR. Los dos ini son tuyos: al actualizar se conservan tus valores y se añaden las opciones nuevas. Todo se monta y se valida en el temporal, así que si una compilación falla lo anterior queda intacto; tampoco quedan restos, y si la versión instalada ya es la última no se recompila. Companion también comprueba la última versión estable (con caché de una hora) y, si la tuya es anterior, el botón pasa a ser *Actualizar HelixSR (anterior → nueva)*. *Copiar HelixSR al juego* pone todo eso en `C:\windows\system32\umu` del prefijo del juego, más los enlaces `dxgi.dll` y `d3d12.dll` a `OptiScaler.dll`, y la opción añade `WINE_OPTISCALER_NAME=dxgi.dll`: la Wine de GE-Proton / proton-cachyos carga OptiScaler desde ahí sin tocar la carpeta del juego. No uses `PROTON_USE_OPTISCALER` con HelixSR: Proton pondría su propio OptiScaler en ese `umu`. Si el juego ya tiene ahí el OptiScaler de Proton, se mueve a `umu.proton` (o `umu.proton-<fecha>`) para poder volver a él, y lo que dejaban versiones anteriores del módulo en `C:\HelixSR` se borra (su `helixsr.ini` se aprovecha). La copia solo se propone si al juego le falta algo, tiene el OptiScaler de Proton o restos en `C:\HelixSR`, o no tiene `.version` o es anterior a la instalada; los ini del juego se fusionan (se conservan sus valores y se añaden las opciones nuevas). La descarga es una tarea pesada: aparece como tarea en el panel **Tasks** de Invasor (Select en el panel de Invasor) con su progreso, se ejecuta de una en una y se rechaza mientras hay un juego en ejecución.
- **Juego**: todo lo que los archivos de Steam dicen del juego actual (la página abierta; si no, el resaltado; si no, el
  que se está ejecutando), agrupado en secciones: general, instalación (biblioteca, carpeta, tamaño, estado, compilación, actualizaciones), juego (última
  partida, tiempo de juego, opciones de lanzamiento), compatibilidad (herramienta, prefijo) y, para los accesos directos que no son de Steam, su ejecutable, directorio
  de inicio y etiquetas, además de los enlaces a la tienda y a SteamDB. Al pulsar una fila se copia su valor (también el AppID).
- **Steam**: elige cualquier archivo (un explorador que empieza en tu carpeta personal, con cualquier extensión) y pulsa *Añadir a Steam*. Le pide
  a Steam que lo añada como juego que no es de Steam de la forma que Steam admite: crea `/tmp/addnonsteamgamefile` y abre
  `steam://addnonsteamgame/<ruta codificada>` con `xdg-open`. `xdg-open` se ejecuta con el entorno de la sesión gráfica (el servicio no tiene ninguno) y se comprueba su resultado. Steam muestra su propio diálogo de confirmación; después el módulo espera a que el acceso directo aparezca en `shortcuts.vdf`.
  Debajo, una sección plegada **Limpieza** lista las carpetas `compatdata`/`shadercache` de juegos que ya no están instalados (en todas las bibliotecas) y las imágenes de `userdata/*/config/grid` que no son de ningún juego ni acceso directo. Todo viene marcado; tú eliges y confirmas, y solo se borran elementos de un análisis recién hecho. Los nombres de los juegos se recuerdan en `~/.local/share/invasor/companion/names.json` (se actualizan en cada inicio de Steam) para que una carpeta sobrante diga qué era.
- **Créditos**: el autor.

Los textos siguen el idioma de Steam (español o inglés). La lógica es un port del lanzador Companion de
`../companion`; solo construye el texto y nunca toca los ficheros del juego; lo único que escribe en un juego es *Copiar HelixSR al juego*, en su prefijo (`C:\windows\system32\umu`) y solo cuando lo pulsas.

## Requisitos
Invasor 0.2.0 o posterior (`min_core`): usa `ctx.task` y `ctx.events`.

## Compilar, probar e instalar
Con el núcleo descargado junto a este repositorio (`../invasor`):

```sh
python3 ../invasor/tools/pack_module.py companion       # comprueba, tests -> companion-<versión>.zip
python3 ../invasor/tools/install_module.py companion    # o instala ese zip desde ⚙ Ajustes › Instalar módulo
```

## Licencia
[GNU General Public License v3.0 o posterior](LICENSE) (GPL-3.0-or-later).
