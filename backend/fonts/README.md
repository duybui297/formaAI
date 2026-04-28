# Noto Fonts Bundle

Required for fpdf2 explicit font registration (D-04-27).

Files expected in this directory:
- `NotoSans-Regular.ttf`     (~500KB)  — Latin/Vietnamese glyphs
- `NotoSansCJK-Regular.ttc` (~48MB)   — Japanese/Chinese/Korean glyphs

These binary files are NOT committed to git (see .gitignore).
They must be placed here before building the Docker image.

## Download sources

- `NotoSans-Regular.ttf`:
  https://github.com/notofonts/latin-greek-cyrillic/releases
- `NotoSansCJK-Regular.ttc`:
  https://github.com/notofonts/noto-cjk/releases

## Why explicit paths?

fpdf2's `add_font()` requires explicit file paths. The system apt Noto fonts
(installed via `apt-get install fonts-noto-cjk fonts-noto`) are available for
PyMuPDF/fontconfig use, but their paths vary by distro and are not reliable for
fpdf2's direct registration. This bundle provides a known, stable path:

```python
pdf.add_font("NotoSans", fname="/backend/fonts/NotoSans-Regular.ttf")
pdf.add_font("NotoSansCJK", fname="/backend/fonts/NotoSansCJK-Regular.ttc")
```

## CI setup

In CI, fetch fonts in the Dockerfile or via a setup script before the
`COPY backend/fonts/` layer runs. Example:

```bash
curl -L -o backend/fonts/NotoSans-Regular.ttf \
  "https://github.com/notofonts/latin-greek-cyrillic/releases/download/NotoSans-v2.013/NotoSans-Regular.ttf"
```
