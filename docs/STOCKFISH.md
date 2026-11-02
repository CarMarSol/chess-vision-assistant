# Fuentes correspondientes de Stockfish

El ejecutable actual es **Stockfish 17 AVX2 oficial**, comprobado byte por byte contra el paquete de la Release `sf_17` de `official-stockfish/Stockfish`. No se ha sustituido ni modificado el motor.

Las fuentes completas de la etiqueta, la licencia y los autores se incluyen en [third_party/stockfish](../third_party/stockfish/README.md). El ZIP fuente ocupa unos 272 KB e incluye el Makefile, scripts, pruebas y flujos originales de compilación. El manifiesto [provenance.json](../third_party/stockfish/provenance.json) registra el commit, las URL y los hashes.

## Descarga del motor verificado

Desde la raíz del proyecto puedes instalar el motor con un solo comando, sin dependencias adicionales:

```powershell
python -m scripts.install_stockfish
```

El instalador comprueba los hashes del ZIP y del ejecutable antes de colocarlo en `bin/stockfish.exe`. No sustituye un motor diferente salvo que añadas `--replace` expresamente. Requiere un procesador compatible con AVX2. La descarga sucede al ejecutar el comando, nunca al importar módulos.

También puedes instalarlo manualmente:

1. Descarga [stockfish-windows-x86-64-avx2.zip de Stockfish 17](https://github.com/official-stockfish/Stockfish/releases/download/sf_17/stockfish-windows-x86-64-avx2.zip).
2. Comprueba que tu procesador soporta AVX2. Para otra arquitectura utiliza una compilación compatible; al redistribuirla hay que actualizar también la procedencia y su verificación.
3. Extrae el ejecutable y colócalo como `bin/stockfish.exe` para usarlo con la aplicación.
4. Verifica su hash:

```powershell
Get-FileHash .\bin\stockfish.exe -Algorithm SHA256
```

El resultado esperado es:

```text
0b24c22f7894fa13ab27e32a29763055d0867dfb123d8763579dea5b7a91f419
```

La fuente identificada es el commit `e0bfc4b69bbe928d6f474a46560bcc3b3f6709aa`. Las 59 fuentes incluidas en el paquete binario coinciden con el archivo de ese commit normalizando los finales de línea. El propio ejecutable declara MinGW64/g++ 14.1.0, arquitectura `x86-64-avx2`.

## Compilación y redistribución

El [README de fuentes](../third_party/stockfish/README.md) explica cómo extraerlas, descargar las dos redes NNUE exactas mediante `make net` y compilar con MSYS2/MinGW64. Los procedimientos de compilación originales están dentro del ZIP. No se ha recompilado Stockfish ni se afirma una reproducción idéntica byte por byte de la compilación original.

`build_exe.py` comprueba el hash del ejecutable y de las fuentes/avisos antes de crear una distribución, y añade el directorio `third_party/stockfish` al paquete y junto al ejecutable. Así se conservan las fuentes correspondientes, licencia, autores y procedencia al distribuir este motor concreto. Cambiar de motor exige actualizar esos elementos.

El motor sigue siendo software de sus autores bajo GPL; el proyecto no se atribuye su desarrollo. Referencias oficiales: [Release Stockfish 17](https://github.com/official-stockfish/Stockfish/releases/tag/sf_17), [fuentes exactas](https://github.com/official-stockfish/Stockfish/tree/e0bfc4b69bbe928d6f474a46560bcc3b3f6709aa), [condiciones de distribución](https://stockfishchess.org/about/#about-the-gpl).
