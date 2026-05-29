# Build guide — docscanner AppImage

This document describes how to build a self-contained AppImage for docscanner.

---

## Table of contents

- [Overview](#overview)
- [Build dependencies](#build-dependencies)
- [Build](#build)
- [Output](#output)
- [How it works](#how-it-works)
- [Known issues](#known-issues)
- [Inspect and debug](#inspect-and-debug)
- [End-user requirements](#end-user-requirements)

---

## Overview

The build pipeline:

```
entrypoint.py
     │
     ▼
PyInstaller ──► dist/docscanner      (single binary, Python + deps bundled)
                     │
                     ▼
              linuxdeploy ──► AppDir/  (binary + shared libs + SANE backends)
                                  │
                                  ▼
                           appimagetool ──► docscanner-x86_64.AppImage
```

---

## Build dependencies

The following must be installed **on the build machine** before running the build script.
The script checks for all of these and exits with a clear message if anything is missing.

| Dependency | Why needed | Install |
|---|---|---|
| `uv` | Run PyInstaller in the project venv | https://docs.astral.sh/uv/ |
| `wget` | Download linuxdeploy on first run | `apt install wget` / `pacman -S wget` |
| `pyinstaller` | Bundle Python into a single binary | `uv add --dev pyinstaller` |
| `libsane-fujitsu.so` | Copied into AppImage for scanner backend | `apt install sane-utils` / `pacman -S sane` |
| `libMagickWand.so` | Bundled by linuxdeploy for image optimization | `apt install libmagickwand-dev` / `pacman -S imagemagick` |
| `magick` / `convert` | Resize icon to 256x256 for AppImage | included with ImageMagick |

`linuxdeploy` is downloaded automatically on the first build.

---

## Build

Run from the **project root**:

```bash
./build/build-appimage.sh
```

The script is fully self-contained. On the first run it downloads `linuxdeploy`.
Subsequent runs reuse it.

---

## Output

```
docscanner-x86_64.AppImage    ← on x86_64
docscanner-aarch64.AppImage   ← on Raspberry Pi (aarch64)
```

The AppImage is placed in the project root directory.

---

## How it works

### 1. PyInstaller

`entrypoint.py` is used as the entry point (not `src/de/boebelix/app.py` directly).

**Why not `app.py` directly?**  
PyInstaller treats any module named `main.py` as the `__main__` module, which strips
its package context and breaks relative imports (`from .button import ...`).
Using a thin `entrypoint.py` that imports `from de.boebelix.app import main` avoids
this conflict entirely.

**Why not `run.py`?**  
`run.py` manipulates `sys.path` to find `src/` — this path doesn't exist inside the
PyInstaller bundle. `entrypoint.py` has no path manipulation; `--paths src` passes
the source root to PyInstaller directly.

### 2. SANE backends

SANE loads scanner backends (e.g. `libsane-fujitsu.so`) dynamically at runtime via
`dlopen`. These are invisible to `ldd`, so linuxdeploy cannot find them automatically.
The build script copies them manually into `AppDir/usr/lib/sane/`.

`AppRun` sets the environment so the bundled backends are found:

```sh
export LD_LIBRARY_PATH="$APPDIR/usr/lib/sane:$LD_LIBRARY_PATH"
export SANE_CONFIG_DIR="$APPDIR/etc/sane.d"
```

### 3. linuxdeploy + NO_STRIP

linuxdeploy bundles all shared libraries found via `ldd` (libsane, libMagickWand, etc.)
and sets `$ORIGIN` rpaths so the AppImage finds them at runtime.

`NO_STRIP=1` is required on CachyOS and other modern distributions because linuxdeploy
ships an outdated `strip` binary that cannot process ELF files with `.relr.dyn` sections.

### 4. Icon

The source image is not a standard AppImage resolution. The build script resizes it to
256x256 using `magick` before passing it to linuxdeploy.

### 5. AppDir cleanup

`AppDir/` is deleted at the start of every build (`rm -rf "$APPDIR"`). Without this,
linuxdeploy may reuse stale binaries from a previous build, causing the AppImage to
silently run old code.

---

## Known issues

### Namespace package (de/)

`src/de/` has no `__init__.py` (it is a PEP 420 implicit namespace package). PyInstaller
does not reliably handle implicit namespace packages. An empty `src/de/__init__.py` is
required for the bundle to import `de.boebelix` correctly.

### img2pdf

`img2pdf` is called as a Python library (`import img2pdf`), **not** as a subprocess.
Calling `subprocess.run(["img2pdf", ...])` would fail inside the AppImage because no
`img2pdf` binary exists on the user's PATH.

---

## Inspect and debug

Extract the AppImage contents:

```bash
./docscanner-x86_64.AppImage --appimage-extract
# → squashfs-root/
```

Run the extracted binary directly (useful for debugging without AppImage overhead):

```bash
./squashfs-root/usr/bin/docscanner
```

Run the PyInstaller binary directly (without AppImage wrapping):

```bash
./dist/docscanner
```

---

## End-user requirements

libMagickWand and libsane are **bundled inside the AppImage** — users do not need to
install them. The only runtime requirement is SANE for USB device access and udev rules:

```bash
# Debian / Ubuntu / Raspberry Pi OS
sudo apt install sane-utils

# Arch / CachyOS / Manjaro
sudo pacman -S sane
```
