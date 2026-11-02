# Componentes y recursos de terceros

Revisado el 2 de noviembre de 2026. El código original del proyecto se ofrece bajo **GPL-3.0-or-later**; los componentes ajenos conservan su autoría y licencia.

## Stockfish 17

Autoría: los desarrolladores listados en [AUTHORS](third_party/stockfish/AUTHORS). Licencia: [GPL versión 3 o posterior](third_party/stockfish/Copying.txt).

El ejecutable local se ha comparado byte por byte con el del [paquete oficial Stockfish 17 AVX2](https://github.com/official-stockfish/Stockfish/releases/tag/sf_17). Las 59 fuentes incluidas en ese paquete coinciden con el commit `e0bfc4b69bbe928d6f474a46560bcc3b3f6709aa`, normalizando los finales de línea.

En [third_party/stockfish](third_party/stockfish/README.md) se incluyen el archivo de fuentes completo de ese commit, la licencia, los autores, el registro de procedencia y los hashes. El [manual del motor](docs/STOCKFISH.md) explica la instalación verificada, las redes NNUE necesarias y los procedimientos originales de compilación. No se ha recompilado el motor ni se garantiza una reproducción bit a bit con otro entorno.

La distribución de código para GitHub omite el ejecutable y ofrece `python -m scripts.install_stockfish` para descargarlo verificando ZIP y ejecutable. `build_exe.py` verifica los hashes antes de empaquetar y conserva el directorio `third_party` con el programa. Si distribuyes otro motor, actualiza sus fuentes correspondientes y su procedencia. [Condiciones oficiales](https://stockfishchess.org/about/#about-the-gpl).

## Piezas cburnett

Copyright **Colin M. L. Burnett**. Las doce fuentes SVG originales se obtuvieron sin cambios del [repositorio oficial de Lichess, commit fijado](https://github.com/lichess-org/lila/tree/5b44d719ec5913dd62aa965f4b8d21e60a00c2c1/public/piece/cburnett).

El registro upstream atribuye explícitamente ese directorio a su autor bajo **GPL-2.0-or-later**. Esta distribución opta por **GPL-3.0-or-later**. No se describe el material como dominio público. Las fuentes, los hashes de cada SVG, el registro upstream y la licencia completa están en [third_party/chess_pieces](third_party/chess_pieces/README.md).

La interfaz incorpora los mismos SVG originales para funcionar sin conexión. Las máscaras de reconocimiento públicas son derivados generados a partir del canal alfa de esos SVG; su generador y sus pruebas están incluidos. El historial y las modificaciones se describen en el README de las piezas.

## Referencias privadas que no se exportan

La copia de desarrollo puede conservar capturas en `tests/fixtures/`, imágenes de depuración, PNG/NPZ de `data/templates/` y máscaras Neo incrustadas en su módulo de plantillas. No se ha acreditado el permiso para redistribuir ese conjunto. Una captura o una transformación de gráficos no acredita por sí sola esos derechos.

`scripts/prepare_publication.py` **no copia esas imágenes ni la base Neo** y sustituye el módulo de plantillas de la copia pública por `scripts/public_piece_templates.py`, generado exclusivamente a partir de los SVG cburnett verificados. Los módulos de regresión que requieren el corpus privado no se exportan y quedan enumerados en `PUBLICATION_MANIFEST.json`. Se incluyen pruebas públicas sintéticas con las piezas autorizadas.

Por eso se debe publicar desde la carpeta generada y no hacer un `git push` de toda la copia de desarrollo. Si incorporas nuevas capturas o referencias, comprueba sus permisos, elimina datos personales, registra la procedencia y añade pruebas. Consulta [Diseños de piezas y reconocimiento](docs/PIEZAS_Y_RECONOCIMIENTO.md).

## Bibliotecas

| Componente | Uso | Licencia o referencia |
| --- | --- | --- |
| python-chess (`chess`) | Reglas, FEN, Polyglot y UCI | [GPL-3.0-or-later](https://python-chess.readthedocs.io/en/latest/#license) |
| PySide6 / Qt | Interfaz | [Licencias de Qt](https://doc.qt.io/qt-6/licensing.html), [Qt for Python](https://doc.qt.io/qtforpython-6.11/commercial/index.html) |
| OpenCV / opencv-python | Visión | [OpenCV](https://github.com/opencv/opencv), [paquete Python](https://github.com/opencv/opencv-python) |
| NumPy | Cálculo sobre imágenes | [Licencia de NumPy](https://numpy.org/doc/stable/license.html) y avisos de bibliotecas incluidas |
| MSS | Captura | [Proyecto y licencia MIT](https://github.com/BoboTiG/python-mss) |
| PyInstaller | Empaquetado | [Licencia y excepción de distribución](https://pyinstaller.org/en/stable/license.html) |

La tabla no sustituye los textos de licencia de los paquetes y DLL que incorpores a una distribución ejecutable. Conserva sus avisos y verifica las dependencias transitivas efectivamente distribuidas.

## Libro de aperturas

La preparación pública regenera `data/openings.bin` desde el catálogo `CURATED_OPENINGS` del código, usando su compilador Polyglot. No copia el binario de la carpeta de trabajo. Si amplías ese catálogo desde otra base, documenta su procedencia y licencia.
