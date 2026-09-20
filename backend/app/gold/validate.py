"""
YojanSetu - Day 28: Direct CLI Entrypoint for Dataset Validation.

Usage:
  python -m app.gold.validate [--version v1]
"""

import argparse
import sys
from app.gold.cli import run_validate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate YojanSetu Gold Dataset")
    parser.add_argument("--version", default="v1", help="Dataset version folder (default: v1)")
    args = parser.parse_args()
    run_validate(args)
