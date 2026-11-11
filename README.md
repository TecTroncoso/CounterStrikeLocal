# Counter-Strike 1.6 en el navegador

Port de Counter-Strike 1.6 para el navegador, basado en el motor
[Xash3D-FWGS](https://github.com/FWGS/xash3d-fwgs) compilado para WebAssembly y en la
biblioteca cliente [cs16-client](https://www.npmjs.com/package/cs16-client).

El juego se ejecuta enteramente en el cliente: los archivos del juego se descargan
por partes, se descomprimen en un sistema de archivos virtual y el motor se
inicia **después** de que todos los recursos están en su sitio.

## Cómo funciona

1. `valve-parts/manifest.json` describe las partes de 8 MiB del `valve.zip`.
2. El navegador descarga las partes en paralelo (4 a la vez; `?parallel=`
   permite de 1 a 8), comprueba el SHA-256 de cada una y monta el ZIP en
   memoria. Las URLs llevan el hash, así que el navegador puede cachearlas
   indefinidamente.
3. El ZIP se descomprime con JSZip y se escribe en el disco virtual de
   Emscripten, en `/rodir/valve/` y `/rodir/cstrike/`.
4. Solo entonces se inicia el motor (`em.start()`), porque el motor busca el
   directorio del juego en cuanto se ejecuta el `main`.

Los archivos no se escriben dentro de `onRuntimeInitialized` (asíncrono)
mientras `callMain()` ya arrancó el motor: eso hacía que el juego abortara con
`Couldn't find game directory 'cstrike'`. Aquí se espera a que todos los
recursos estén completos antes de llamar a `em.start()`.

## Requisitos

- Python 3.9 o superior (para `serve.py` y el despliegue).
- Solo para regenerar los recursos: una copia de Counter-Strike 1.6 (Steam)
  instalada en local.

El repositorio ya incluye `vendor/` y `valve-parts/`, así que un clon funciona
sin descargar nada más. `valve.zip` no se versiona: es el archivo intermedio que
se usa para regenerar las partes.

## Preparación

Estos pasos solo hacen falta si quieres actualizar `vendor/` o regenerar
`valve-parts/` a partir de tu propia instalación del juego.

### 1. Descargar las dependencias de runtime

```bash
python scripts/fetch-vendor.py
```

El script descarga el motor (`xash3d-fwgs@1.2.1`), las bibliotecas de CS 1.6
(`cs16-client@0.1.2`) y el JSZip a `vendor/`, verificando el SHA-256 de cada
archivo.

### 2. Crear el `valve.zip` a partir de la instalación local

```bash
python scripts/build-valve-zip.py --install "C:\games\Counter-Strike 1.6" --out valve.zip
```

El script empaqueta las carpetas `valve/` y `cstrike/` de la instalación
(ignorando `cstrike_hd`, `htmlcache`, `crashes` y `platform`) e informa del
tamaño resultante. También omite las librerías nativas `.so`, `.dll`,
`.dylib` y `.pdb`: el cliente web carga las bibliotecas del juego desde los
módulos WebAssembly de `vendor/` y nunca abre las nativas. Usa
`--keep-native` si el mismo archivo va a alimentar una build nativa.

Si ya tienes un `valve.zip` pero no la instalación, `scripts/prune-valve-zip.py`
aplica ese mismo recorte sobre el archivo existente y lo recomprime:

```bash
python scripts/prune-valve-zip.py
```

Después de cambiar el contenido del archivo hay que regenerar las partes y el
manifiesto con `scripts/split-valve-parts.py`.

### 3. Dividir el archivo en partes

```bash
python scripts/split-valve-parts.py
```

Genera `valve-parts/valve.part-000…` y el `valve-parts/manifest.json` que usa
el cliente.

### 4. Reconstruir el `valve.zip` desde las partes

El `valve.zip` no se versiona (249 MB: GitHub rechaza archivos de más de
100 MB y el repositorio ya contiene todos los bytes repartidos en las 32
partes). Si lo necesitas como archivo único, se reconstruye desde el repo:

```bash
python scripts/join-valve-parts.py
```

El script verifica el SHA-256 contra el manifiesto y solo escribe el archivo
si todo cuadra.

## Qué se versiona

| Ruta | ¿En el repo? | Motivo |
| --- | --- | --- |
| `index.html`, `config.js`, `loopback-net.js`, `_headers`, `favicon.ico` | Sí | cliente y configuración de despliegue |
| `scripts/` | Sí | regenerar recursos y desplegar |
| `vendor/` | Sí | runtime necesario para jugar (~32 MB) |
| `valve-parts/` | Sí | payload del juego (~248 MB) |
| `valve.zip` | No | intermedio y redundante: las partes ya contienen los mismos datos |
| `.env` | No | secretos locales |
| `dist/` | No | salida generada por el despliegue |

## Levantar el servidor

El servidor estático ya está listo; basta con ejecutarlo desde la raíz del
proyecto:

```bash
cd /ruta/al/proyecto/Counter-Strike
python scripts/serve.py --port 8080
```

Sirve la carpeta del proyecto (el `index.html`, el `valve-parts/`, el
`vendor/`) y se queda escuchando hasta que pulses `Ctrl+C`. Después abre:

| Dirección                                      | Qué hace                                            |
| ---------------------------------------------- | --------------------------------------------------- |
| <http://127.0.0.1:8080/>                      | Pantalla de inicio y partida automática con 9 bots  |
| <http://127.0.0.1:8080/?map=de_inferno&bots=9> | Empieza en `de_inferno` con 9 bots                   |
| <http://127.0.0.1:8080/?autostart=0>          | Muestra la pantalla de inicio sin cuenta atrás       |
| <http://127.0.0.1:8080/?developer=2>          | Muestra el log del motor en la consola              |

Opciones de `scripts/serve.py`:

```
--port 8080        puerto (por defecto: 8080)
--host 127.0.0.1   interfaz de escucha; usa 0.0.0.0 para entrar desde el
                    móvil o desde otro equipo de la red local
```

Ejemplo para jugar en el móvil (misma Wi-Fi):

```bash
python scripts/serve.py --host 0.0.0.0 --port 8080
```

y abre en el móvil `http://<ip-del-pc>:8080/`.

`serve.py` no sirve archivos ni carpetas que empiecen por punto, así que `.env`
(con el token de Cloudflare) y `.git` no quedan expuestos en la red local.

Servir por HTTP es obligatorio: el motor se carga vía `fetch`/WebAssembly y el
navegador bloquea eso en `file://`.

### Cómo jugar

1. Abre la URL de arriba y espera a que la barra de progreso termine de
   descargar y descomprimir los recursos.
2. La pantalla de inicio muestra la rotación y una cuenta atrás de 3 segundos:
   la partida arranca sola. También puedes pulsar **JUGAR** para entrar al
   instante.
3. El jugador entra siempre en el equipo Terrorista: son **9 bots + tú**, cinco
   contra cinco. El HUD de la página muestra el mapa actual, el siguiente y el
   tamaño del equipo.
4. Haz clic sobre el canvas para capturar el ratón. La tecla **`** (acento
   grave) abre la consola del motor, donde puedes ejecutar `bot_add_ct`,
   `bot_add_t`, `bot_quota 9`, `exec touch/buy.cfg`, etc.
5. Cuando cualquiera de los dos equipos gana una ronda, el mapa cambia solo al
   siguiente de la rotación (ver más abajo). El botón de pantalla completa está
   en la esquina del HUD.
6. Para salir de la partida: `disconnect` en la consola.

Si la página deja de cargar, reinicia el servidor (`Ctrl+C` y vuelve a lanzarlo):
el `ThreadingTCPServer` llena la cola de conexiones si el navegador deja
muchas conexiones abiertas y hace falta reiniciarlo.

## Despliegue en Cloudflare Pages

Todo el juego es estático, así que Cloudflare Pages Free es suficiente: no hay
backend, no hay CORS (mismo origen) y las partes de 8 MiB caben bajo el límite
de 25 MiB por archivo. El plan Free de Pages no pide tarjeta.

1. Crea un token de API con el permiso **Cloudflare Pages: Edit**.
2. Copia `.env.example` a `.env` y rellena las tres variables:

   ```bash
   CLOUDFLARE_API_TOKEN=...
   CLOUDFLARE_ACCOUNT_ID=...
   PAGES_PROJECT=cs16-browser
   ```

3. Ejecuta el despliegue:

   ```bash
   bash scripts/deploy-cloudflare.sh
   ```

El script comprueba Python 3, `node` y `npx`, descarga `vendor/` si falta,
construye un `dist/` limpio (sin `.git`, `valve.zip`, scripts ni
documentación), genera `dist/config.js` con `PARTS_BASE_URL`, crea el proyecto
si todavía no existe y ejecuta `wrangler pages deploy`. La URL final es
`https://<PAGES_PROJECT>.pages.dev`.

`bash scripts/deploy-cloudflare.sh --dry-run` construye `dist/` sin subirlo.

### Caché

`_headers` marca las partes y `vendor/` como inmutables durante un año. Cada
parte se pide con `?v=<12 primeros caracteres del SHA-256>`, y los archivos de
`vendor/` con `?v=<versión del paquete>`; así un cambio de contenido siempre es
una URL nueva. `manifest.json`, `index.html`, `config.js` y `loopback-net.js`
se revalidan siempre. Resultado: la primera visita descarga ~280 MB; las
siguientes reutilizan las partes y `extras.pk3` desde la caché. Si actualizas
un paquete de `vendor/`, sube `XASH_VERSION`/`CS16_VERSION` en `index.html`.

### R2 (opcional)

Solo hace falta si algún día usas archivos de más de 25 MiB, superas 20.000
archivos o quieres actualizar las partes sin redesplegar el sitio. En ese caso
pon la URL pública de R2 en `PARTS_BASE_URL` (con barra final) y permite CORS
desde el dominio de Pages. R2 Free da 10 GB-mes y 10 millones de lecturas al
mes, pero activarlo puede pedir tarjeta.

### Aviso legal

El repositorio y el sitio publicado incluyen assets de Valve en `valve-parts/`,
así que el proyecto redistribuye contenido del juego. Para un proyecto personal
o de prueba el riesgo es bajo; para algo público necesitas otra estrategia (por
ejemplo, que cada usuario genere sus propias partes). Ningún hosting gratuito
cambia eso.

## Parámetros de la URL

| Parámetro           | Efecto                                                                 |
| ------------------- | ---------------------------------------------------------------------- |
| `?map=de_inferno`   | Empieza en ese mapa y coloca la rotación a partir de él.               |
| `?bots=9`           | Número de bots (0–15; por defecto 9).                                   |
| `?maxplayers=10`    | Plazas del servidor local (2–16; por defecto 10, mínimo `bots + 1`).    |
| `?difficulty=2`     | Dificultad de los bots (0–3; por defecto 2).                            |
| `?parallel=4`       | Descargas simultáneas de partes (1–8; por defecto 4).                   |
| `?autostart=0`      | Desactiva la cuenta atrás: la partida espera a que pulses **JUGAR**.    |
| `?scale=0.7`        | Fija la escala de render (0.5–1). `auto` la ajusta sola.                |
| `?developer=2`      | Activa el log detallado del motor (`-dev 2`; por defecto `-dev 1`).     |
| `?classic=1`        | Fuerza el menú clásico (por defecto en escritorio). `?classic=0` fuerza el táctil. |

El `?map=` se ejecuta desde JavaScript (`Cmd_ExecuteString`) y no con `+map` en
la línea de comandos: el motor solo ejecuta los argumentos `+comando` cuando
algún `.rc` llama a `stuffcmds`, y Counter-Strike 1.6 no tiene `cstrike.rc` —
solo `valve/valve.rc`, y el motor lo busca únicamente dentro del directorio del
juego.

## Rotación de mapas

La rotación por defecto es:

```
de_dust2 → de_inferno → de_aztec → de_nuke → de_train
→ de_cbble → de_prodigy → cs_office → cs_italy → de_dust → (vuelve a de_dust2)
```

- Al empezar, el HUD muestra el mapa actual y el siguiente. El mapa de arranque
  se puede cambiar con `?map=`; la rotación continúa desde ahí.
- Formato competitivo MR15: `mp_maxrounds 30` (gana el primero en llegar a 16
  rondas). `mp_winlimit 16` arma ese límite al entrar el jugador; mientras la
  pantalla de inicio está visible el límite vale 0, para que un bot no pueda
  ganar y cambiar el mapa antes de que entres.
- El motor lee `cstrike/mapcycle.txt` como una cola circular y empieza por la
  primera entrada, no por la siguiente al mapa actual. Por eso la página genera
  el archivo desplazado una posición (`[siguiente, ..., último, actual]`): así
  el primer cambio va al mapa que anuncia el HUD y el último vuelve al primero.
- El cambio tarda unos 10–13 segundos: aparece un overlay con el aviso, el
  servidor se reinicia, se reconstruyen los 9 bots (5 CT + 4 T), el jugador
  vuelve a Terrorista y se rearma el límite de una ronda.
- Si el mapa pedido no está en `MAP_ROTATION` pero sí en el archivo del juego,
  se usa como punto de partida y la rotación sigue con los mapas por defecto.

## Bots

El motor viene con `maxplayers 1` — un servidor de un solo jugador local — así
que el servidor no tenía ni una plaza libre y `bot_add` respondía
`Unable to create bot: Server is full (1/1 clients)`. El valor se inyecta en el
`config.cfg` antes de que suba el servidor (es un cvar *latched*, o sea, solo
puede cambiar con el servidor parado).

La ventana "Create Server" del menú no se abre en el port web (es una ventana
del VGUI del motor y la biblioteca de soporte del VGUI no está publicada), así
que los bots se añaden por consola:

```
bot_add_ct      # añade un bot Counter-Terrorist
bot_add_t       # añade un bot Terrorist
bot_quota 9     # cuota de bots
```

La página lo hace sola: por defecto añade 5 bots CT y 4 T, y te deja a ti en
Terrorista para un 5 contra 5. Se puede cambiar con `?bots=N` (máximo 15).
Cada plaza de jugador consume memoria y el heap de WebAssembly es fijo (256 MB,
sin crecimiento), por lo que `?maxplayers=` tiene un límite práctico de ~8 a 16.

Tras cada cambio de mapa el servidor arranca de nuevo con los bots anteriores
todavía conectados. La página pone `bot_quota 0` en cuanto ve `Spawn Server:`,
expulsa a los que quedan, espera a que el motor libere las plazas y vuelve a
crear la misma formación. Así no aparecen errores `Server is full` ni se pierde
ningún bot en la rotación.

## Detalles que hacen que el juego funcione

El motor en WebAssembly carga las bibliotecas del juego como *side modules* de
Emscripten, y cada una tiene que cargarse con el nombre exacto que pide el
motor — un módulo que solo se puede resolver por `locateFile` no carga de
forma síncrona cuando arranca el servidor:

| Biblioteca                  | Nombre que usa el motor (1.2.1)         |
| --------------------------- | --------------------------------------- |
| sistema de archivos         | `filesystem_stdio.wasm`                  |
| menú de CS                  | `cl_dlls/menu_emscripten_wasm32.wasm`   |
| biblioteca cliente          | `cl_dlls/client_emscripten_wasm32.wasm` |
| biblioteca del juego (servidor) | `dlls/cs_emscripten_wasm32.so`       |
| renderizador                | `libref_webgl2.wasm`                    |

Dos detalles rompen la partida si se quedan fuera:

- **`dlls/cs_emscripten_wasm32.so`** — el motor pide la biblioteca del juego por
  el nombre del mod (`cs`) y con la extensión `.so`. Sin ese nombre exacto en
  `dynamicLibraries` el servidor ni siquiera arranca:
  `SV_LoadProgs: failed to get address of GetEntityAPI proc`.
- **`/rodir/filesystem_stdio.wasm`** — cuando ya se conoce el directorio del
  juego, el motor abre el módulo del sistema de archivos por la ruta absoluta.
  Si esa carga falla, el motor se queda con un puntero de función nulo y la
  partida muere en el primer frame con `RuntimeError: null function`. Por eso
  el módulo se precarga con el nombre simple **y** con la ruta absoluta.

La ventana del motor también tiene que tener el tamaño del canvas, si no el
viewport queda raro. Eso se hace con `-width`/`-height`, que el motor acepta en
la línea de comandos, y el canvas se dimensiona en 4:3 (la proporción clásica)
con píxeles enteros.

## Escalado dinámico de resolución

El motor dibuja la escena 3D en una ventana de su propio tamaño; el canvas se
muestra en otro (el que cabe en la ventana del navegador) y el navegador escala
la imagen. Renderizar por debajo del tamaño final reduce el *fill rate*, que es
lo que ahoga a las GPUs integradas y a los móviles.

Por defecto la página mide el tiempo entre frames y baja la escala sola cuando
el motor no llega (pasos de 1 → 0.85 → 0.7 → 0.6 → 0.5). Para fijarla:
`?scale=0.7` (o `?scale=auto` para dejarla automática).

Detalles de la implementación:

- La referencia es el intervalo de `requestAnimationFrame` mientras se mide el
  *refresh rate* del display (los primeros frames, con el menú en pantalla). Con
  eso se distingue "el navegador va a 30 Hz" de "el motor va a 30 fps".
- Se usa la mediana de los últimos segundos, así que un tirón puntual (carga de
  mapa, garbage collection) no baja la resolución.
- Bajar la escala necesita dos mediciones seguidas y subirla cuatro, más una
  pausa de 30 s después de bajar: así se asienta en la menor resolución que
  todavía da los fps y no oscila.
- El tamaño se aplica con los cvars `width` y `height`, que son
  `FCVAR_VIDRESTART`: el motor vuelve a aplicar el modo de vídeo y redimensiona
  el canvas. Ni `vid_mode` ni `-width`/`-height` funcionan en el build de
  WebAssembly.

En el navegador se ve el cambio en la consola: `[cs16] render 746x559 (escala
0.70)`.

## Comprar armas

El paquete `cs16-client` no incluye el menú VGUI nativo: cuando el servidor
manda un menú VGUI, el cliente cae en el menú táctil (`touch/buy.cfg`). Ese
menú está pensado para tocar la pantalla; las teclas numéricas no lo navegan y
el servidor ignora sus `menuselect` mientras `_vgui_menus` está activo, así que
pulsar **1** o **4** lo cierra en vez de navegar.

Por eso, en escritorio se usa por defecto el menú clásico (`_vgui_menus 0`):

- **B** abre el menú.
- **1** abre la categoría de pistolas; **4** compra la Desert Eagle (si hay
  dinero). El dinero y el arma se actualizan en el servidor.
- **0** cierra el menú.

En móvil/tablet se mantiene el menú táctil, que se maneja tocando los botones:
**B** lo abre, un toque en la categoría entra en ella y el botón *BUY THE ITEM*
confirma la compra. `?classic=1` fuerza el menú clásico y `?classic=0` fuerza el
táctil.

El cliente abre el menú solo al aparecer. En el modo táctil la página lo cierra
1,6 segundos después con `client_buy_close` para dejar la vista limpia; en el
modo clásico se deja abierto, porque cerrarlo podría coincidir con una pulsación
de **B** justo después de aparecer. En cualquier caso se puede volver a abrir
cuando quieras.

## Estado actual

- El menú principal y los submenús funcionan.
- La pantalla de inicio descarga los recursos, muestra la rotación y arranca la
  partida sola con una cuenta atrás de 3 segundos (o al pulsar **JUGAR**).
- La partida local funciona: el servidor de escucha arranca, el mapa se carga,
  el cliente se conecta (`client connected at 0.13 sec`) y el teclado y el ratón
  llegan al juego.
- Los 9 bots entran y juegan (5 CT + 4 T + tú); tras cada cambio de mapa la
  formación se reconstruye sola.
- Al ganar una ronda cualquiera de los dos equipos el mapa rota
  automáticamente y el HUD anuncia el siguiente.
- La resolución de render se ajusta sola para mantener los fps (ver "Escalado
  dinámico de resolución"); se puede fijar con `?scale=`.
- Las partes se piden con URLs versionadas y `_headers` las cachea un año; la
  segunda visita no vuelve a descargar el archivo. El despliegue está
  preparado para Cloudflare Pages (`scripts/deploy-cloudflare.sh`).
- El HUD propio de la página (mapa actual, siguiente mapa, tamaño del equipo,
  ayuda de controles y botón de pantalla completa) funciona en escritorio y
  móvil. El HUD del motor (salud, munición, radar) no se dibuja: la biblioteca
  cliente lo pinta con el VGUI del motor y la biblioteca de soporte del VGUI
  (`libvgui_support.wasm`) no está publicada en ningún paquete — ni en
  `xash3d-fwgs`, ni en `cs16-client`. La consola del motor (tecla `` ` ``)
  funciona con normalidad.
- El soporte de VGUI es parcial: solo se puede abrir una ventana de VGUI a la
  vez (el menú principal, los submenús y la consola del motor).

## Estructura

```
index.html                 cliente (escrito a mano, sin paso de build)
config.js                  URL de las partes (la genera el despliegue)
_headers                   cabeceras de caché para Cloudflare Pages
loopback-net.js            capa de sockets mínima para el motor
scripts/
  build-valve-zip.py       crea el valve.zip a partir de la instalación local
  prune-valve-zip.py       recorta un valve.zip existente (sin la instalación)
  split-valve-parts.py     divide el valve.zip y genera el manifiesto
  join-valve-parts.py      reconstruye el valve.zip desde las partes
  fetch-vendor.py          descarga y verifica las dependencias de runtime
  serve.py                 servidor estático local
  deploy-cloudflare.sh     construye dist/ y despliega en Cloudflare Pages
.env.example               plantilla de las variables de despliegue
.gitignore                 exclusiones (valve.zip, .env, dist, cachés)
.gitattributes             normalización de saltos de línea
bash.bat                   lanzador de OpenCode en Windows
valve-parts/               partes del valve.zip + manifest.json (versionadas)
vendor/                    motor, bibliotecas de CS 1.6 y JSZip (versionadas)
valve.zip                  archivo intermedio, ignorado por Git
```

## Créditos y licencias

- Motor: [Xash3D-FWGS](https://github.com/FWGS/xash3d-fwgs).
- Biblioteca cliente: [cs16-client](https://www.npmjs.com/package/cs16-client).
- Counter-Strike 1.6, Half-Life y sus archivos son © Valve Corporation. Este
  proyecto no está afiliado a Valve. `valve-parts/` contiene assets del juego y
  se incluye con fines personales y educativos; si publicas el repositorio o el
  sitio, revisa los términos de Valve.
