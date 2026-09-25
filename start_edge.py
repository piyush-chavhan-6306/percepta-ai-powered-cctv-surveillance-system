#!/usr/bin/env python3
"""
PERCEPTA — Hybrid Edge Launch Script
=====================================

Starts the local PERCEPTA edge node and optionally exposes it via ngrok
so that the Vercel Cloud C2 can reach live YOLO perception.

Usage:
    # Offline-only (no tunnel, local C2 only):
    python start_edge.py

    # Online with public tunnel (enables Vercel C2 → live YOLO):
    NGROK_AUTHTOKEN=<your_token> python start_edge.py --tunnel

    # With existing ngrok auth in ngrok config:
    python start_edge.py --tunnel

Architecture:
    LOCAL MACHINE (this script)
        ├─ FastAPI Edge (port 8000)
        │    ├─ Camera Manager
        │    ├─ YOLO / YOLOv8n ONNX
        │    ├─ ByteTrack / Kalman
        │    ├─ ANPR / Face / Weapon
        │    ├─ Zones / Tripwires
        │    ├─ Threat Engine
        │    ├─ Incidents / Evidence
        │    ├─ SQLite (WAL)
        │    └─ WebSocket /ws/events
        │
        └─ ngrok tunnel → https://XXXXX.ngrok-free.app
                               │
                         INTERNET
                               │
                    Vercel Cloud C2
                    (percepta-one.vercel.app)
                         ↓ fetch to edge URL
                    Real YOLO telemetry
"""

import argparse
import asyncio
import logging
import os
import sys
import threading
import time
from pathlib import Path

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("percepta.edge")


# ─── Ensure venv is active ────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent
VENV_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = REPO_ROOT / "venv" / "bin" / "python"

if sys.prefix == sys.base_prefix:
    logger.warning(
        "Not running inside a venv. Activate: venv\\Scripts\\activate.bat"
    )


# ─── Ngrok tunnel ─────────────────────────────────────────────────────────────
def start_ngrok_tunnel(port: int = 8000, auth_token: str | None = None) -> str | None:
    """Start an ngrok HTTPS tunnel and return the public URL."""
    try:
        from pyngrok import ngrok, conf

        if auth_token:
            ngrok.set_auth_token(auth_token)
        elif os.environ.get("NGROK_AUTHTOKEN"):
            ngrok.set_auth_token(os.environ["NGROK_AUTHTOKEN"])

        logger.info(f"[TUNNEL] Starting ngrok tunnel on port {port} ...")
        tunnel = ngrok.connect(port, "http", bind_tls=True)
        public_url = tunnel.public_url
        logger.info(f"[TUNNEL] ✅  Public URL: {public_url}")

        # Write edge URL to a well-known local file so the frontend dev server
        # can pick it up, and so operators can copy it into the Vercel env var.
        edge_url_file = REPO_ROOT / "runtime" / "edge_url.txt"
        edge_url_file.parent.mkdir(parents=True, exist_ok=True)
        edge_url_file.write_text(public_url.strip())

        # Also write as a .env variable hint
        env_hint = REPO_ROOT / "runtime" / "EDGE_URL.env"
        env_hint.write_text(f"VITE_API_URL={public_url}\n")

        print("\n" + "=" * 60)
        print("  PERCEPTA EDGE — ONLINE MODE ACTIVE")
        print("=" * 60)
        print(f"  Local FastAPI:   http://127.0.0.1:{port}")
        print(f"  Public URL:      {public_url}")
        print()
        print("  To wire the Vercel C2 to this edge node:")
        print(f"  vercel env add VITE_API_URL {public_url} production")
        print()
        print("  Alternatively set this as VITE_API_URL in your browser:")
        print(f"  localStorage.setItem('percepta_backend_url', '{public_url}')")
        print("=" * 60 + "\n")

        return public_url

    except ImportError:
        logger.error("[TUNNEL] pyngrok not installed. Run: pip install pyngrok")
        return None
    except Exception as e:
        logger.warning(f"[TUNNEL] Could not start ngrok tunnel: {e}")
        logger.warning("[TUNNEL] Running in LOCAL MODE ONLY (no public URL)")
        return None


# ─── Health check ─────────────────────────────────────────────────────────────
def wait_for_backend(port: int = 8000, timeout: int = 30) -> bool:
    """Poll /api/health until the FastAPI server is ready."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
            if r.status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PERCEPTA Edge Node Launcher")
    parser.add_argument(
        "--tunnel",
        action="store_true",
        default=False,
        help="Expose local edge via ngrok for Vercel Cloud C2 access",
    )
    parser.add_argument(
        "--ngrok-token",
        default=None,
        help="ngrok auth token (or set NGROK_AUTHTOKEN env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Local FastAPI port (default: 8000)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Uvicorn worker processes (default: 1 for asyncio camera I/O)",
    )
    args = parser.parse_args()

    os.chdir(REPO_ROOT)  # Ensure relative paths work correctly

    public_url: str | None = None

    # ── Step 1: Start ngrok BEFORE uvicorn so the URL is available early ─────
    if args.tunnel:
        public_url = start_ngrok_tunnel(
            port=args.port,
            auth_token=args.ngrok_token or os.environ.get("NGROK_AUTHTOKEN"),
        )

    if not args.tunnel:
        print("\n" + "=" * 60)
        print("  PERCEPTA EDGE — LOCAL MODE")
        print("=" * 60)
        print(f"  FastAPI:    http://127.0.0.1:{args.port}")
        print(f"  Local C2:   http://127.0.0.1:{args.port}")
        print()
        print("  To enable public online access, restart with --tunnel:")
        print("  python start_edge.py --tunnel")
        print("=" * 60 + "\n")

    # ── Step 2: Start Uvicorn ─────────────────────────────────────────────────
    import uvicorn
    config = uvicorn.Config(
        "backend.main:app",
        host="0.0.0.0",
        port=args.port,
        log_level="info",
        workers=args.workers,
        reload=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    logger.info(f"[EDGE] Starting PERCEPTA FastAPI Edge on port {args.port} ...")
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("[EDGE] PERCEPTA Edge Node shutting down.")
    finally:
        if args.tunnel:
            try:
                from pyngrok import ngrok
                ngrok.kill()
                logger.info("[TUNNEL] ngrok tunnel closed.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
