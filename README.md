# Chess Vision Assistant

Aplicación de escritorio para Windows que reconoce un tablero visible en pantalla y muestra análisis local con Stockfish. Está pensada para estudiar posiciones y revisar partidas terminadas, o para usarla en entornos donde la asistencia esté permitida. No necesita cuenta ni API externa.

## Instalar en Windows

La beta 1.0.0-beta.1 está preparada para **Windows x64 con AVX2**. Cuando se publique la [Release en GitHub](docs/PUBLICACION_GITHUB.md), elige una de estas opciones:

### Opción recomendada: instalador

1. Descarga `ChessVisionAssistant-1.0.0-beta.1-Windows-Setup.exe` desde la sección **Assets** de la Release.
2. Abre el archivo y pulsa **Instalar**.
3. Inicia Chess Vision Assistant desde el acceso directo del escritorio o del menú Inicio.

No necesitas instalar Python, pip ni Stockfish por separado, ni tener conexión después de descargar el instalador. Se instala en tu perfil de Windows y no requiere permisos de administrador. Antes de actualizar, cierra la aplicación. Luego ejecuta el instalador de la nueva versión sobre la instalación existente; tus preferencias se conservan. Antes de desinstalar, cierra la aplicación y usa **Desinstalar** en la carpeta de instalación o en el menú Inicio; esto no elimina tus preferencias.

El instalador de beta no está firmado digitalmente. Si Windows muestra SmartScreen, comprueba que el nombre del archivo coincide con el publicado en la Release y consulta sus instrucciones habituales; no desactives la protección de Windows.

### Alternativa: versión portable

1. Descarga `ChessVisionAssistant-1.0.0-beta.1-Windows-Portable.zip` desde **Assets**.
2. Extrae el ZIP completo a una carpeta con permisos de escritura.
3. Abre `ChessVisionAssistant.exe` dentro de esa carpeta.

No ejecutes la aplicación directamente desde la vista previa del ZIP ni muevas el EXE fuera de la carpeta extraída: necesita los archivos que lo acompañan. La versión portable también incluye Python y Stockfish y funciona sin conexión.

Los paquetes anteriores se deben considerar disponibles solo cuando aparezcan como adjuntos en la Release. Si todavía no están allí, puedes usar la instalación desde código fuente descrita más abajo.

## Requisitos y limitaciones

- Windows de 64 bits y procesador compatible con AVX2. La beta distribuida contiene una compilación AVX2 de Stockfish.
- No requiere Python para instalar o ejecutar los paquetes de Release.
- Las piezas exóticas, estilizadas o distintas de cburnett pueden no reconocerse bien. Revisa la posición detectada antes de interpretar el análisis; puedes corregir piezas y FEN manualmente. Consulta [Diseños de piezas y reconocimiento](docs/PIEZAS_Y_RECONOCIMIENTO.md) para adaptar el reconocimiento con referencias autorizadas.
- Una captura aislada no siempre permite deducir el turno, derechos de enroque o captura al paso. Si cambias tamaño o posición de la ventana, selecciona de nuevo la región del tablero.
- Cuatro tableros y un esfuerzo de análisis alto usan más CPU y memoria.

Si el procesador no admite AVX2, estos paquetes no son adecuados. Desde el código fuente se puede configurar otro ejecutable UCI compatible con el procesador; la guía está en [Stockfish](docs/STOCKFISH.md).

## Funciones

- Selección de la región del tablero con retícula y lupa.
- Reconocimiento de piezas, orientación y seguimiento de movimientos legales.
- Análisis de hasta tres variantes con Stockfish, flechas y barra de evaluación.
- Entre uno y cuatro tableros con configuración individual.
- Tablero independiente y superposición de indicaciones.
- Corrección manual de piezas, turno y posición mediante FEN.
- Libro de aperturas, temas claro/oscuro y colores configurables.
- Interfaz en español, inglés, francés, portugués y alemán. El selector está arriba; el cambio se aplica al reiniciar y se guarda.
- Simulador de posiciones para probar el análisis sin capturar un navegador.

Las etiquetas «brillante», «gran jugada» y similares son heurísticas del proyecto. El Elo simulado y la precisión son estimaciones, sin equivalencia garantizada con plataformas ni clasificaciones humanas.

## Primer uso

1. Abre **Simulador de Partidas** para comprobar el análisis con una posición de prueba.
2. Para capturar un tablero, abre **Asistente de Inicio / Modos**, elige el número de tableros y el modo de visualización.
3. Pulsa **Seleccionar región** o **Recortar** y delimita solo las 64 casillas.
4. Confirma la perspectiva de blancas o negras y revisa las piezas detectadas.
5. Corrige la posición o el FEN si hace falta antes de interpretar las variantes.

## Instalación desde el código fuente

Esta opción es para desarrollo o para procesadores que requieren otra compilación del motor. Requiere Python 3.11 de 64 bits, conexión para instalar dependencias y un motor Stockfish compatible. Descarga o clona la copia pública indicada en la [guía de publicación](docs/PUBLICACION_GITHUB.md), abre PowerShell en su carpeta y ejecuta:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.install_stockfish
.\.venv\Scripts\python.exe main.py --test-engine
.\.venv\Scripts\python.exe main.py
```

El instalador de Stockfish descarga y verifica la versión oficial 17 AVX2. Requiere CPU compatible. Para otro motor puedes indicarlo con `--stockfish-path "C:\ruta\stockfish.exe"`. Las fuentes, licencia y procedencia de Stockfish están en `third_party/stockfish/` y [docs/STOCKFISH.md](docs/STOCKFISH.md).

La configuración normal se guarda en `%APPDATA%\ChessVisionAssistant\settings.json`. El selector de idioma está en la barra superior; también se puede iniciar desde código con `--language en` (códigos: `es`, `en`, `fr`, `pt`, `de`).

## Desarrollo y pruebas

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:QT_QPA_PLATFORM = "offscreen"
$env:APPDATA = Join-Path $PWD ".test-appdata"
.\.venv\Scripts\python.exe -u -m pytest -v tests
```

Ejecuta las pruebas en una PowerShell dedicada: `APPDATA` se redirige para no sobrescribir preferencias habituales. Para preparar la copia pública, ejecuta `python -m scripts.prepare_publication`; revisa el manifiesto y publica desde `publicacion/chess-vision-assistant/`, no desde la carpeta de desarrollo, que puede contener referencias y capturas privadas.

## Uso responsable

Las recomendaciones de un motor durante una partida pueden incumplir las normas de la plataforma, incluso en partidas sin clasificación. Úsalo para estudio, análisis posterior o donde la asistencia esté expresamente permitida. Consulta las políticas de [Chess.com](https://www.chess.com/legal/fair-play) y [Lichess](https://lichess.org/page/fair-play). El proyecto no está afiliado a esas plataformas ni al equipo de Stockfish.

## Licencia y créditos

El código original se ofrece bajo **GPL-3.0-or-later** ([LICENSE](LICENSE)). Componentes y recursos de terceros conservan sus condiciones; sus avisos están en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). La distribución pública incluye piezas cburnett verificadas y sus atribuciones; no distribuye capturas privadas ni referencias Neo no autorizadas.

Para informar un fallo, indica versión de Windows, pasos para reproducir, resultado esperado y obtenido, resolución, escalado, tema y orientación. Antes de adjuntar capturas, elimina nombres, chats y otros datos personales.
