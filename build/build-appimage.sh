#!/bin/bash
set -e

# Run from project root: ./build/build-appimage.sh
BUILD_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$BUILD_DIR/.." && pwd)"

ARCH=$(uname -m)
APPDIR="$PROJECT_ROOT/AppDir"
APPIMAGE_NAME="$PROJECT_ROOT/docscanner-${ARCH}.AppImage"
LINUXDEPLOY="$BUILD_DIR/linuxdeploy-${ARCH}.AppImage"

cd "$PROJECT_ROOT"

# ── 0. Build-time dependency check ──────────────────────────────────────────
# Only checks what is needed to BUILD the AppImage.
# Runtime requirements for end users are printed at the end.

MISSING=()

command -v uv   &>/dev/null || MISSING+=("uv           → https://docs.astral.sh/uv/")
command -v wget &>/dev/null || MISSING+=("wget         → sudo apt install wget  /  sudo pacman -S wget")
uv run pyinstaller --version &>/dev/null || MISSING+=("pyinstaller  → uv add --dev pyinstaller")

# libsane-fujitsu must be present on the build machine to be copied into AppDir
find /usr/lib -name "libsane-fujitsu.so*" 2>/dev/null | grep -q . \
    || MISSING+=("libsane-fujitsu (needed to bundle into AppImage) → sudo apt install sane-utils  /  sudo pacman -S sane")

# libMagickWand must be present for linuxdeploy to bundle it
find /usr/lib -name "libMagickWand*.so*" 2>/dev/null | grep -q . \
    || MISSING+=("libMagickWand (needed to bundle into AppImage) → sudo apt install libmagickwand-dev  /  sudo pacman -S imagemagick")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Missing build dependencies:"
    echo ""
    for item in "${MISSING[@]}"; do
        echo "  ✗  $item"
    done
    echo ""
    exit 1
fi

echo "All build dependencies found."

# ── 1. Download linuxdeploy ──────────────────────────────────────────────────

if [ ! -f "$LINUXDEPLOY" ]; then
    echo "Downloading linuxdeploy..."
    wget -q -O "$LINUXDEPLOY" \
        "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-${ARCH}.AppImage"
    chmod +x "$LINUXDEPLOY"
fi

# ── 2. Python executable ─────────────────────────────────────────────────────

echo "Building executable with PyInstaller..."
uv run pyinstaller --onefile --clean --name docscanner \
    --paths src \
    --specpath "$BUILD_DIR" \
    "$BUILD_DIR/entrypoint.py"

# ── 3. AppDir structure ──────────────────────────────────────────────────────

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib/sane"
mkdir -p "$APPDIR/etc/sane.d"

cp "$BUILD_DIR/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"

cp "$BUILD_DIR/docscanner.desktop" "$APPDIR/docscanner.desktop"

# linuxdeploy requires a standard icon resolution — scale to 256x256
magick "$PROJECT_ROOT/doc/images/Gemini_Generated_Image_5hb2r85hb2r85hb2.png" \
    -resize 256x256! "$APPDIR/docscanner.png"

# ── 4. SANE backends (loaded dynamically at runtime, ldd won't find them) ───

echo "Copying SANE backends..."
SANE_BACKEND_DIR=$(find /usr/lib -name "libsane-fujitsu.so*" 2>/dev/null | head -1 | xargs dirname)
cp "$SANE_BACKEND_DIR"/libsane-fujitsu.so* "$APPDIR/usr/lib/sane/"

[ -f /etc/sane.d/fujitsu.conf ] && cp /etc/sane.d/fujitsu.conf "$APPDIR/etc/sane.d/"
[ -f /etc/sane.d/dll.conf ]     && cp /etc/sane.d/dll.conf     "$APPDIR/etc/sane.d/"

# ── 5. Bundle with linuxdeploy (resolves libsane, libMagickWand, etc.) ───────

echo "Bundling shared libraries with linuxdeploy..."
NO_STRIP=1 "$LINUXDEPLOY" \
    --appdir "$APPDIR" \
    --executable "$PROJECT_ROOT/dist/docscanner" \
    --desktop-file "$BUILD_DIR/docscanner.desktop" \
    --icon-file "$APPDIR/docscanner.png" \
    --output appimage

mv "$PROJECT_ROOT"/docscanner-*.AppImage "$APPIMAGE_NAME" 2>/dev/null || true

# ── 6. End-user requirements ─────────────────────────────────────────────────

echo ""
echo "Done: $APPIMAGE_NAME"
echo ""
echo "End users must install the following on the target system:"
echo "  • sane / sane-utils  (USB access and udev rules for the scanner)"
echo "    Debian/Ubuntu:  sudo apt install sane-utils"
echo "    Arch/CachyOS:   sudo pacman -S sane"
echo ""
echo "  libMagickWand and libsane are bundled inside the AppImage."
