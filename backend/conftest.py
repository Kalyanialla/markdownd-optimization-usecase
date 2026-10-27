import sys
from pathlib import Path

# Ensure root workspace is on sys.path for pytest runs inside backend/
workspace_root = str(Path(__file__).resolve().parents[1])
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
