# cburnett chess artwork

Copyright Colin M. L. Burnett (Cburnett).

These twelve original SVG files were downloaded unchanged from the official
[lichess-org/lila repository](https://github.com/lichess-org/lila/tree/5b44d719ec5913dd62aa965f4b8d21e60a00c2c1/public/piece/cburnett),
at commit `5b44d719ec5913dd62aa965f4b8d21e60a00c2c1`.

The upstream licensing record identifies `public/piece/cburnett` as the work of
Colin M. L. Burnett under **GPL version 2 or later**. The pinned original record is
included as `UPSTREAM_COPYING.md`; its separate commit, source URL and SHA-256
are recorded in `SOURCES.json`. The default AGPL license for the Lila application
does not replace this explicit exception for the cburnett artwork.

This distribution exercises the option to distribute the cburnett artwork and
derived silhouettes under **GPL-3.0-or-later**. The complete GPL version 3 text is
included in `COPYING.GPL-3.0.txt`.

## What was changed

- The SVG source files in this directory are original upstream bytes, with no
  local graphics modifications.
- The exact SVG strings are embedded in `chess_vision/ui/pieces_svg.py` to retain
  offline rendering and compatibility with the existing renderer API.
- The public recognition silhouettes in `scripts/public_piece_templates.py`
  are local derivatives: render each SVG at 128×128 on transparent RGBA, use the
  alpha channel above 127 as its silhouette, scale to 32×32 with nearest-neighbor,
  and pack the resulting bits as base64. The original colors and interior detail
  are not part of these masks.

Regenerate from the original SVG sources with:

```powershell
python third_party/chess_pieces/generate_templates.py
```

The generator verifies the twelve source hashes before writing the template
module. `tests/test_piece_assets.py` checks that embedded SVGs match the original
files and that masks can be regenerated from them. The generator requires the
application's existing PySide6, NumPy and OpenCV dependencies.

The public export copies `scripts/public_piece_templates.py` over
`chess_vision/vision/piece_templates.py`. The development copy keeps its existing
recognition references. The public template module preserves the four helper
APIs; requests for Neo references return an empty mask, and the classifier can
continue using the cburnett masks. This is reduced visual coverage, not universal
recognition of arbitrary pieces.
