# Companion

[English](README.md) · **Español**

Un módulo para [Invasor](../invasor) que **construye las opciones de lanzamiento de Steam de un juego** (`VAR=valor … mangohud mako-launch %command%`)
desde el panel, con el mando, y las copia al portapapeles. Pega el resultado en Propiedades › General ›
Opciones de lanzamiento del juego. Añade una pestaña **Compa** (que no aparece en el Acceso rápido) con cuatro páginas:

- **Lanzador**: una vista previa en vivo del comando y un botón *Copiar* arriba, y después las opciones en secciones:
  FG/escaladores (MAKO, lsfg-vk, FSR 4), MangoHud (límite de FPS, API y FPS), gráficos (wined3d, Zink, HDR, Direct3D),
  Proton (compatibilidad de 32 bits, large address aware, esync/fsync, PROTON LOG = `PROTON_LOG=1` al principio de todo el comando, para que Proton deje `~/steam-<AppID>.log`, prefijo elegido en un explorador de carpetas que empieza en `compatdata` y puede ir a cualquier sitio), entorno (DLL overrides, «no es una Steam Deck» = `SteamDeck=0`, variables personalizadas)
  y *Restablecer todo*. Las combinaciones incompatibles o vacías muestran un aviso. Las elecciones no se guardan: se restablecen al recargar la pestaña.
  MAKO y lsfg-vk se excluyen entre sí: al activar uno se desactiva el otro.
  HelixSR se ha movido al módulo [Opti](https://github.com/Gamemode-Invasor/invasor-opti) (pestaña Opti → Global → Custom DLLs), y la sección de escaladores lo dice donde estaba su interruptor. Lo que instalaron versiones anteriores de Companion no se toca: los juegos con HelixSR Scaler en su prefijo lo conservan, y `~/.local/share/HelixSR/` se puede borrar a mano.
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
`../companion`; solo construye el texto y nunca toca los ficheros del juego.

## Requisitos
Invasor 0.2.0 o posterior (`min_core`): usa `ctx.events`.

## Compilar, probar e instalar
Con el núcleo descargado junto a este repositorio (`../invasor`):

```sh
python3 ../invasor/tools/pack_module.py companion       # comprueba, tests -> companion-<versión>.zip
python3 ../invasor/tools/install_module.py companion    # o instala ese zip desde ⚙ Ajustes › Instalar módulo
```

## Licencia
[GNU General Public License v3.0 o posterior](LICENSE) (GPL-3.0-or-later).
