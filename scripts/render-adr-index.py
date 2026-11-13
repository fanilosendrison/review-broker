"""Render explicitly, or purely check, the ADR index."""
import argparse
from pathlib import Path
from adr_profile_contract import render_index


def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true')
    mode.add_argument('--write',action='store_true')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    expected=render_index(args.root).encode('utf-8')
    destination=args.root/'docs/adr/README.md'
    if args.write:
        destination.write_bytes(expected)
    elif not destination.is_file() or destination.read_bytes()!=expected:
        raise SystemExit('ADR_INDEX_MISSING_OR_STALE')


if __name__=='__main__':
    main()
