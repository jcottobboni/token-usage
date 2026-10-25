import sys
from pathlib import Path

if not __package__ and not getattr(sys, "frozen", False):
    # `python caminho/token_usage` (usado pelo início automático): o pacote não está no sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from token_usage.cli import main  # noqa: E402

main()
