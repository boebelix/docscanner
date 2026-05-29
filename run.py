import sys
from pathlib import Path

src = str(Path(__file__).parent / "src")
if src not in sys.path:
    sys.path.insert(0, src)

from de.boebelix.main import main

main()
