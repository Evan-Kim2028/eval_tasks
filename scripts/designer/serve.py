#!/usr/bin/env python3
"""Serve the designer dashboard on localhost (stdlib only)."""

from __future__ import annotations

import argparse
import http.server
import os
import socketserver
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    os.chdir(HERE)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt: str, *rest) -> None:
            print(f"designer {self.address_string()} {fmt % rest}")

    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"designer http://127.0.0.1:{args.port}/  (jobs.json + index.html)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
