"""
YojanSetu - Day 28: Direct CLI Entrypoint for Dataset Freezing.

Usage:
  python -m app.gold.freeze [--version v1.0]
"""

import argparse
import sys
from app.gold.cli import run_freeze

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Freeze YojanSetu Gold Dataset")
    parser.add_argument("--version", default="v1", help="Dataset version folder (default: v1)")
    args = parser.parse_args()
    run_freeze(args)
