from pathlib import Path

# Resolves to the repository root (the directory containing pyproject.toml),
# regardless of where the process is started from or how the package is installed.
#
# Path chain:
#   __file__              → src/de/boebelix/__init__.py
#   .parents[0]           → src/de/boebelix/
#   .parents[1]           → src/de/
#   .parents[2]           → src/
#   .parents[3]           → <project root>   ← PROJECT_ROOT
#
# Usage:
#   from de.boebelix import PROJECT_ROOT
#   path = PROJECT_ROOT / "queue" / "Scan_001.pdf"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
