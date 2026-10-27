#!/usr/bin/env python3
"""Run the Echoes FastAPI server.

Usage:
    python scripts/server.py
    python scripts/server.py --port 8080 --mock
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn
from echoes.api import state


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1", help="Host interface to bind to")
    ap.add_argument("--port", type=int, default=8000, help="Port to listen on")
    ap.add_argument("--mock", action="store_true", help="Force offline mock server")
    args = ap.parse_args()

    if args.mock:
        state.initialize_client(force_mock=True)

    if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print(f"\n[Echoes] Server starting on http://{args.host}:{args.port}")
    print(f"[Echoes] API Documentation available at http://{args.host}:{args.port}/docs\n")
    uvicorn.run("echoes.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
