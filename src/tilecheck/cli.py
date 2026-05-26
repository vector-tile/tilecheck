"""tilecheck command-line interface."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from tilecheck import __version__
from tilecheck.analyze import Report, analyze
from tilecheck.format import to_json, to_text
from tilecheck.readers import open_archive


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tilecheck",
        description=(
            "Audit PMTiles and MBTiles files: zoom-level size distributions, "
            "oversized-tile warnings, and metadata inspection."
        ),
    )
    parser.add_argument("file", type=Path, help="Path to a .pmtiles or .mbtiles file")
    parser.add_argument(
        "--max-tile-size",
        type=int,
        default=500,
        metavar="KB",
        help="Flag tiles larger than this many KB (default: 500). Use 0 to disable.",
    )
    parser.add_argument(
        "--list-oversized",
        type=int,
        default=20,
        metavar="N",
        help="List up to N largest oversized tiles (default: 20).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of a human-readable summary.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in text output.",
    )
    parser.add_argument(
        "--exit-on-oversized",
        action="store_true",
        help="Exit with status 2 when any oversized tile is found (useful in CI).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"tilecheck {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    path: Path = args.file
    if not path.exists():
        print(f"tilecheck: error: file not found: {path}", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"tilecheck: error: not a regular file: {path}", file=sys.stderr)
        return 1

    try:
        stream = open_archive(path)
    except ValueError as exc:
        print(f"tilecheck: error: {exc}", file=sys.stderr)
        return 1

    threshold_bytes = max(0, args.max_tile_size) * 1024
    zooms, oversized, total_tiles, total_bytes = analyze(
        stream.tiles,
        oversized_threshold=threshold_bytes,
        oversized_limit=max(0, args.list_oversized),
    )
    report = Report(
        format=stream.format,
        path=str(path),
        header=stream.header,
        metadata=stream.metadata,
        zooms=zooms,
        oversized=oversized,
        total_tiles=total_tiles,
        total_bytes=total_bytes,
        oversized_threshold=threshold_bytes,
    )

    if args.json:
        sys.stdout.write(to_json(report) + "\n")
    else:
        use_color = not args.no_color and sys.stdout.isatty() and "NO_COLOR" not in os.environ
        sys.stdout.write(to_text(report, use_color=use_color))

    if args.exit_on_oversized and oversized:
        return 2
    return 0
