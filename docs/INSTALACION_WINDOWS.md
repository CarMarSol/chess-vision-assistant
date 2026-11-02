# Instalación en Windows

La beta 1.0.0-beta.1 está dirigida a Windows x64 y requiere un procesador compatible con AVX2 para el Stockfish incluido. Se distribuye en dos formatos. Ambos incluyen la aplicación, Python, PySide6, OpenCV, Stockfish y los avisos/licencias necesarios; no necesitas instalar Python ni estar conectado a Internet para usarlos.

## Instalador (recomendado)

1. Descarga `ChessVisionAssistant-1.0.0-beta.1-Windows-Setup.exe` desde **Assets** en la página de Releases de GitHub.
2. Ejecuta el archivo y pulsa **Instalar**.
3. Abre Chess Vision Assistant desde el acceso directo del escritorio o del menú Inicio.

Se instala únicamente para tu cuenta, en `%LOCALAPPDATA%\Programs\ChessVisionAssistant`, sin permisos de administrador. El instalador es para esta aplicación y su instalación identificada; no reemplaza instalaciones ajenas. Antes de actualizar, cierra la aplicación. Luego instala la nueva versión en esa misma carpeta; se conservan las preferencias de `%APPDATA%\ChessVisionAssistant\settings.json`.

Antes de desinstalar, cierra la aplicación. Luego usa **Desinstalar** en la carpeta instalada o en el menú Inicio. No aparece como aplicación registrada en Configuración de Windows. Se quitan los archivos de la aplicación y sus accesos directos; el archivo de preferencias queda en `%APPDATA%\ChessVisionAssistant`.

## Versión portable

1. Descarga `ChessVisionAssistant-1.0.0-beta.1-Windows-Portable.zip`.
2. Extrae el ZIP completo a una carpeta donde tu usuario pueda escribir.
3. Abre `ChessVisionAssistant.exe` desde esa carpeta.

No ejecutes el programa desde la vista previa del ZIP ni extraigas solo el EXE: la carpeta completa contiene el motor y las bibliotecas. Puedes mover o borrar la carpeta para quitar la versión portable. La configuración normal de la aplicación se guarda en `%APPDATA%\ChessVisionAssistant\settings.json`.

Los nombres anteriores identifican los adjuntos esperados de la Release. Comprueba que los archivos están publicados antes de descargarlos. `SHA256SUMS.txt`, junto a ellos, permite comprobar sus hashes SHA-256.

## SmartScreen

La beta no tiene firma digital de editor. Windows puede mostrar SmartScreen. Comprueba que descargaste el instalador desde la Release oficial del proyecto y que su nombre coincide con el publicado. No desactives SmartScreen ni otras protecciones del sistema.

## Problemas habituales

- **La aplicación indica que AVX2 no está disponible o Stockfish no arranca:** la versión incluida requiere AVX2. Usa otro equipo compatible o ejecuta desde el código fuente con un motor UCI adecuado a tu CPU; sigue [el manual de Stockfish](STOCKFISH.md). El instalador de esta beta no cambia a otro motor.
- **El tablero se reconoce mal:** selecciona solo las 64 casillas, comprueba la orientación y revisa la posición detectada antes de analizar. Los diseños distintos o exóticos pueden fallar; consulta [Diseños de piezas y reconocimiento](PIEZAS_Y_RECONOCIMIENTO.md).
- **Cambiaste tamaño o ubicación del tablero:** vuelve a seleccionar la región.
- **No se inicia desde ZIP:** extrae primero todo el archivo y ejecuta el EXE dentro de la carpeta extraída.

Al informar un fallo, indica versión de Windows y del paquete, pasos para reproducirlo, resolución y escalado. Si adjuntas una captura, elimina antes cualquier nombre, chat o dato personal.
