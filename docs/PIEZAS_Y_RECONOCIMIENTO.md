# Diseños de piezas y reconocimiento

El reconocimiento visual depende del diseño de las piezas. Si utilizas piezas
con una forma distinta, exótica, decorativa o muy estilizada, **el sistema puede
confundirlas o no reconocerlas**. El tamaño, el escalado de Windows, el zoom,
los colores, las animaciones, las flechas y las casillas resaltadas también
influyen. Una posición detectada incorrectamente puede producir recomendaciones
que no corresponden al tablero real.

## Qué hacer si no reconoce tu tablero

1. Prueba un juego de piezas convencional compatible, preferiblemente cburnett
   para la distribución pública preparada aquí.
2. Mantén visible todo el tablero y recorta solo las 64 casillas, sin relojes,
   encabezados ni márgenes de la página. Vuelve a seleccionar la región si
   cambias el tamaño o la posición de la ventana.
3. Comprueba la perspectiva de blancas/negras, el tema y el zoom. Evita capturar
   un fotograma durante una animación.
4. Revisa las piezas, el turno y la posición. Usa la corrección manual o pega un
   FEN conocido cuando la detección no sea fiable. Una captura aislada no permite
   reconstruir siempre los derechos de enroque o una captura al paso.
5. Si el fallo se repite con ese diseño, se necesitan referencias visuales y
   pruebas de regresión de ese juego de piezas. Elegir un idioma distinto no
   cambia las referencias del clasificador.

## Pedir a tu IA que adapte los archivos

Puedes pedir a la IA que utilices para programar que modifique el proyecto.
Proporciónale capturas recortadas del tablero, su posición correcta en FEN, el
nombre del juego de piezas, zoom, escalado y orientación. Elimina antes nombres,
avatares, conversaciones y cualquier otro dato personal. Utiliza imágenes que
puedas redistribuir si van a formar parte de un repositorio público.

Ejemplo de encargo para copiar y adaptar:

> Adapta Chess Vision Assistant para reconocer este juego de piezas. Te adjunto
> recortes autorizados del tablero y su FEN correcto. Revisa
> `chess_vision/vision/piece_references.py`,
> `chess_vision/vision/piece_templates.py`,
> `chess_vision/vision/piece_classifier.py` y la herramienta
> `scripts/calibrate_neo_references.py`. Añade referencias específicas de este
> diseño sin perjudicar los diseños existentes; no deduzcas una pieza por estar
> en su casilla inicial. Valida las doce clases en casillas diferentes, ambas
> orientaciones, varias resoluciones, capturas y casillas vacías. Añade una
> regresión con capturas redistribuibles y conserva el turno y los derechos de
> enroque del FEN de referencia. Indica exactamente qué diseños has probado y
> qué limitaciones quedan.

La herramienta `calibrate_neo_references.py` actual está calibrada para una
captura concreta y unas coordenadas concretas. No basta con sustituir su imagen
por otra de tamaño arbitrario: hay que adaptar la geometría, la posición
etiquetada y los nombres de los recursos. Una buena adaptación debe separar las
referencias de cada diseño y documentar la licencia y procedencia de sus datos.

## Qué contiene la copia pública

Las doce piezas SVG de la interfaz proceden del juego cburnett de Colin M. L.
Burnett, obtenido del repositorio oficial de Lichess. Su procedencia, versión,
hashes y licencia están en
[third_party/chess_pieces](../third_party/chess_pieces/README.md).

La preparación pública utiliza siluetas generadas exclusivamente desde esos
SVG. Omite las capturas privadas, los PNG/NPZ de referencias Neo y las máscaras
Neo incrustadas cuya redistribución no estaba documentada. La copia de trabajo
local conserva sus referencias existentes. Por tanto, la copia pública puede
reconocer menos diseños que la copia de desarrollo; eso debe comprobarse con tu
tablero antes de interpretar su análisis.

El corpus de regresión con capturas privadas no se distribuye como si fuera un
conjunto de imágenes libre. Las pruebas públicas deben indicar qué datos
incluyen y no presentar la ausencia de ese corpus como una validación de Neo o
de cualquier diseño exótico.
