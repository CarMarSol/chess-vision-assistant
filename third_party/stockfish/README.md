# Stockfish 17: corresponding source and notices

Stockfish is copyright its authors listed in `AUTHORS` and is distributed under the GNU GPL, version 3 or later. The original license is in `Copying.txt`. No Stockfish source changes were made for Chess Vision Assistant.

## Verified binary

The project's `bin/stockfish.exe` was compared byte for byte with `stockfish/stockfish-windows-x86-64-avx2.exe` in the [official Stockfish 17 release package](https://github.com/official-stockfish/Stockfish/releases/download/sf_17/stockfish-windows-x86-64-avx2.zip). They are identical.

- Executable SHA-256: `0b24c22f7894fa13ab27e32a29763055d0867dfb123d8763579dea5b7a91f419`.
- Official release ZIP SHA-256: `918ef7568b23d5f1a22ec188eefe7a2b19aa2fc81f132bafc60c58669c1b7d12`.
- Tag: `sf_17`.
- Commit: `e0bfc4b69bbe928d6f474a46560bcc3b3f6709aa`.
- Source archive: `stockfish-17-source.zip` in this directory.
- Source archive SHA-256: `fb605c29d37ef5a8bd4a3c85c2a17e577cdbcb7ec649f2c74411574d6f6a5c46`.
- [Source at the exact commit](https://github.com/official-stockfish/Stockfish/tree/e0bfc4b69bbe928d6f474a46560bcc3b3f6709aa).

All 59 source files shipped in the official binary package match the included commit archive after normalizing line endings. The archive also includes upstream scripts, tests and build workflows. `provenance.json` records the URLs, hashes and observed compiler information.

## Building the source

Extract `stockfish-17-source.zip`. Read its original README and the build instructions in the upstream documentation. On Windows, use an MSYS2/MinGW64 build environment with GNU make and a suitable C++ compiler. The verified executable reports g++/MinGW64 14.1.0 and architecture `x86-64-avx2`.

From the extracted `src` directory, the upstream Makefile supports:

```sh
make net
make -j profile-build ARCH=x86-64-avx2 COMP=mingw
make strip ARCH=x86-64-avx2 COMP=mingw
```

The two NNUE networks used by this source version are:

- `nn-1111cefa1111.nnue`: [official network file](https://tests.stockfishchess.org/api/nn/nn-1111cefa1111.nnue).
- `nn-37f18f62d772.nnue`: [official network file](https://tests.stockfishchess.org/api/nn/nn-37f18f62d772.nnue).

The Makefile downloads and validates these named networks; its fallback is the official `official-stockfish/networks` repository. Binary releases embed the networks. The network files are not duplicated in this small source archive, so the `make net` step needs network access. The engine's `export_net` command can also save its embedded networks.

The included `.github/workflows/` records the original build and release procedures. A fresh compilation was not performed here and bit-for-bit reproducibility with a different build environment is not claimed.

## Redistribution

When distributing the verified Stockfish executable, preserve this entire directory with the executable, including the source ZIP, license, author list and provenance. `build_exe.py` verifies the executable/source hashes before packaging and copies this directory into the distribution. If the motor is replaced, update the corresponding source and provenance before building a release.

The source-only GitHub distribution can omit the executable and direct users to the verified official package. This source bundle remains included so that the sources and notices are available with the project.
