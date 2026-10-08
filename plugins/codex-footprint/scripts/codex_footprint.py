#!/usr/bin/env python3
"""Relocatable source entrypoint; no installation or third-party dependencies."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from codex_footprint.cli import main
if __name__=='__main__':
    raise SystemExit(main())
