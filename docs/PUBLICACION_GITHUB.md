# Publicar en GitHub

Guía para preparar el código público y adjuntar los paquetes Windows de **Chess Vision Assistant 1.0.0-beta.1**. El repositorio acordado es [CarMarSol/chess-vision-assistant](https://github.com/CarMarSol/chess-vision-assistant), pero aún no está publicado ni conectado a esta copia. Cuando esté disponible, su [página de Releases](https://github.com/CarMarSol/chess-vision-assistant/releases) será el destino de los binarios.

## Preparar el código fuente público

Desde la raíz de esta copia, con Python y las dependencias del proyecto instaladas, ejecuta:

```powershell
python -m scripts.prepare_publication
```

Se generan `publicacion/chess-vision-assistant/` y `publicacion/chess-vision-assistant.zip`. El ZIP contiene código fuente y no incluye los ejecutables Windows. La exportación excluye `.git`, compilaciones, preferencias, capturas privadas y referencias Neo; usa las plantillas públicas cburnett y escribe un `PUBLICATION_MANIFEST.json` con hashes. Revisa la carpeta exportada y el manifiesto antes de publicarlos. No subas el historial de la copia de desarrollo: puede contener binarios y archivos privados aunque hoy estén ignorados.

## Generar los adjuntos para Windows

En un Windows x64 compatible con AVX2, con el motor oficial Stockfish 17 verificado instalado en `bin/stockfish.exe`, ejecuta desde la raíz del proyecto:

```powershell
python -m scripts.build_windows_release --source publicacion/chess-vision-assistant --output publicacion/windows-release --stockfish-path bin/stockfish.exe
```

El comando vuelve a comprobar/exportar el código público y genera en `publicacion/windows-release/`:

- `ChessVisionAssistant-1.0.0-beta.1-Windows-Setup.exe`
- `ChessVisionAssistant-1.0.0-beta.1-Windows-Portable.zip`
- `SHA256SUMS.txt`

Antes de subirlos, confirma que los tres archivos existen, comprueba los hashes contra `SHA256SUMS.txt` y prueba Setup y Portable en un Windows limpio con AVX2. Revisa también que la instalación y actualización mantengan las preferencias, y que la desinstalación no las borre. El Setup no está firmado digitalmente; no indiques que está firmado. Conserva todos los textos de licencia y avisos de terceros incluidos en los paquetes.

Estos paquetes no forman parte del commit del código fuente. No añadas `publicacion/windows-release/` a Git.

## Subir la copia pública

Primero revisa el contenido exportado y su manifiesto. Abre PowerShell dentro de `publicacion/chess-vision-assistant/` y ejecuta:

```powershell
git init -b main
git add .
git diff --cached --stat
git diff --cached --name-only
git commit -m "Publicación inicial de Chess Vision Assistant"
git remote add origin https://github.com/CarMarSol/chess-vision-assistant.git
git push -u origin main
git tag -a v1.0.0-beta.1 -m "Primera beta pública"
git push origin v1.0.0-beta.1
```

Antes del commit, confirma que solo estás publicando la carpeta exportada: no debe contener ejecutables Windows, preferencias ni imágenes privadas. GitHub debe tener creado el repositorio vacío con ese nombre. La autenticación se realiza con los mecanismos de GitHub; no guardes tokens en la URL ni en el proyecto.

## Crear la Release

1. Cuando el repositorio esté conectado y la etiqueta se haya subido, abre la [página de Releases](https://github.com/CarMarSol/chess-vision-assistant/releases).
2. Crea la Release para `v1.0.0-beta.1` y márcala como **pre-release**.
3. Adjunta los dos paquetes Windows y `SHA256SUMS.txt` como assets de esa Release.
4. Publica las notas con requisitos, instrucciones de instalación, limitación AVX2 y reconocimiento de piezas, e indica que es una beta sin firma digital.
5. Comprueba desde la página pública que los tres assets se descargan y que la guía de [instalación](INSTALACION_WINDOWS.md) coincide con sus nombres.

La acción existente de GitHub Actions ejecuta pruebas en Windows cuando corresponda; no genera estos paquetes. No describas como ejecutadas pruebas, compilaciones o subidas que no hayas realizado. El archivo `.zip` de código fuente de GitHub y `publicacion/chess-vision-assistant.zip` son distribuciones de código fuente, distintas de los dos paquetes ejecutables.

## Alcance del paquete

La versión pública incluye recursos visuales cburnett verificados; piezas de otros diseños pueden fallar. La exportación evita imágenes privadas y referencias Neo cuya redistribución no se ha acreditado. Consulta [Diseños de piezas y reconocimiento](PIEZAS_Y_RECONOCIMIENTO.md) para instrucciones de adaptación con referencias que tengas derecho a usar. El paquete incluye el motor Stockfish AVX2 y sus fuentes/licencias correspondientes; consulta [Stockfish](STOCKFISH.md) y [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

Chess Vision Assistant está pensado para estudio y análisis posterior, o para entornos que permitan explícitamente la asistencia de motores. Revisa las reglas de la plataforma antes de usarlo durante una partida.

## Dónde anunciarlo

Fuentes consultadas el 2 de noviembre de 2026. Las prioridades expresan una recomendación por afinidad; no garantizan aceptación ni difusión. Comprueba de nuevo las normas al publicar.

| Prioridad | Comunidad | Cómo encaja y condiciones |
| --- | --- | --- |
| 1 | [TalkChess — General Topics](https://talkchess.com/viewforum.php?f=2) | Foro especializado en software de ajedrez con anuncios de versiones. Presenta el funcionamiento, arquitectura, limitaciones y código; lee su Charter antes de abrir el hilo. |
| 2 | [r/madeinpython](https://www.reddit.com/r/madeinpython/) | Sus reglas admiten creaciones en Python y piden publicaciones detalladas. Cuenta qué problema resuelve, cómo usa Python y qué feedback buscas. |
| 3 | [r/Python](https://www.reddit.com/r/Python/) | La regla actual «No showcase posts» dirige las presentaciones al hilo mensual de showcase o al diario apropiado. Usa ese hilo y el idioma inglés; no abras un anuncio independiente basándote en las reglas antiguas de flairs. |
| 4 | [Hacker News — Show HN](https://news.ycombinator.com/showhn.html) | Adecuado cuando otras personas puedan probarlo fácilmente. Explica qué has construido y por qué; título que empiece por `Show HN:`. Sus normas piden trabajo personal sustancial y desaconsejan prototipos rápidos generados sin elaboración. |
| Secundaria, español | [Foros Ajedrecista](https://www.ajedrecista.com/foros/index.php) | La sección «Ajedrez: Extras» incluye software. La actividad visible es menor que en las opciones anteriores y no se ha confirmado una regla que autorice anuncios de proyectos; consulta sus normas o moderación primero. |

No priorizaría [r/chess](https://www.reddit.com/r/chess/wiki/rules/) para esta primera promoción: aunque permite ciertos anuncios de software gratuito, también prohíbe facilitar trampas. Por las funciones de asistencia y ajuste de precisión, conviene consultar moderación antes de anunciarlo allí. Tampoco usaría el foro de [Lichess](https://lichess.org/page/forum-etiquette) como canal publicitario: sus normas rechazan los mensajes puramente promocionales. Chess Stack Exchange es un sitio de preguntas y respuestas, no un tablón de anuncios; sus [normas de autopromoción](https://chess.stackexchange.com/help/behavior) exigen aportaciones relevantes y revelar la afiliación.

## Borrador para anunciarlo

Úsalo cuando el repositorio sea público y los pendientes estén resueltos. Sustituye la URL y adapta el idioma y formato a cada comunidad. Describe con honestidad el proceso de desarrollo, incluida la asistencia de IA cuando corresponda; no atribuyas validaciones que no hayas realizado.

**Español**

> He creado Chess Vision Assistant, una aplicación de escritorio para Windows que reconoce un tablero visible en pantalla y muestra análisis local con Stockfish. Utiliza Python, PySide6 y OpenCV e incluye edición FEN, hasta cuatro tableros y un simulador de posiciones. Está pensada para estudiar y revisar partidas terminadas, o para entornos donde la asistencia esté permitida.
>
> Publico una primera beta y busco feedback sobre reconocimiento de piezas, escalado y facilidad de instalación. A diferencia de introducir una posición a mano en un analizador, aquí se intenta reconstruir visualmente el tablero; esa parte depende del tema y puede necesitar correcciones.
>
> Código, requisitos, licencia y limitaciones: https://github.com/TU_USUARIO/chess-vision-assistant

**English**

> I built Chess Vision Assistant, a Windows desktop application that recognizes a chessboard on screen and displays local Stockfish analysis. It uses Python, PySide6 and OpenCV, with FEN editing, up to four boards and a position simulator. It is intended for study, post-game review and environments where engine assistance is explicitly allowed.
>
> This is an initial beta. I am looking for feedback on piece recognition, display scaling and installation. Instead of entering the position manually, the application tries to reconstruct it visually; recognition depends on the piece set and may need manual corrections.
>
> Source, setup instructions, license and known limitations: https://github.com/TU_USUARIO/chess-vision-assistant

Para el hilo de r/Python organiza el texto en `What My Project Does`, `Target Audience` y `Comparison`, conforme a las indicaciones de presentación que mantiene su página de reglas. Añade una demostración corta y responde a los problemas reproducibles que lleguen; no publiques el mismo anuncio de forma repetida.
