import sys
from pathlib import Path

# Add the apps/api directory to sys.path so 'app' can be resolved
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
