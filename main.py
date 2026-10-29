"""Vercel entrypoint for the Echoes FastAPI application."""
import sys
from pathlib import Path

# Add 'src' directory to Python path
ROOT = Path(__file__).resolve().parent
src_dir = str(ROOT / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from echoes.api import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="[IP_ADDRESS]", port=8000, reload=True)
