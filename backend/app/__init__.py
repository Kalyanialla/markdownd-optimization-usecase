import sys
from pathlib import Path

# Automatically ensure parent workspace directory is on sys.path
workspace_root = str(Path(__file__).resolve().parents[2])
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
