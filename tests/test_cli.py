"""Smoke tests covering argparse wiring and analyze() aggregation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tilecheck.analyze import analyze
from tilecheck.cli import main


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "tilecheck" in out


def test_missing_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    result = main([str(tmp_path / "does-not-exist.pmtiles")])
    assert result == 1
    assert "file not found" in capsys.readouterr().err


def test_unsupported_extension(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    bogus = tmp_path / "tiles.txt"
    bogus.write_text("not a tile archive")
    result = main([str(bogus)])
    assert result == 1
    assert "Unsupported file type" in capsys.readouterr().err


def test_analyze_aggregates_sizes() -> None:
    stream = [
        (0, 0, 0, 100),
        (1, 0, 0, 200),
        (1, 1, 0, 1_000_000),  # oversized
        (1, 0, 1, 50),
    ]
    zooms, oversized, total_tiles, total_bytes = analyze(
        stream, oversized_threshold=500_000, oversized_limit=10
    )
    assert total_tiles == 4
    assert total_bytes == 1_000_350
    assert [z.zoom for z in zooms] == [0, 1]
    z1 = next(z for z in zooms if z.zoom == 1)
    assert z1.count == 3
    assert z1.min_bytes == 50
    assert z1.max_bytes == 1_000_000
    assert z1.max_tile == (1, 1, 0)
    assert len(oversized) == 1
    assert oversized[0].size == 1_000_000


def test_analyze_oversized_threshold_disabled() -> None:
    stream = [(0, 0, 0, 999_999)]
    _, oversized, _, _ = analyze(stream, oversized_threshold=0)
    assert oversized == []


def test_mbtiles_smoke(tmp_path: Path) -> None:
    """End-to-end: build a tiny MBTiles fixture, run the CLI in JSON mode."""
    import sqlite3

    mbtiles = tmp_path / "fixture.mbtiles"
    conn = sqlite3.connect(mbtiles)
    conn.executescript(
        """
        CREATE TABLE metadata (name TEXT, value TEXT);
        CREATE TABLE tiles (
            zoom_level INTEGER,
            tile_column INTEGER,
            tile_row INTEGER,
            tile_data BLOB
        );
        """
    )
    conn.executemany(
        "INSERT INTO metadata VALUES (?, ?)",
        [
            ("name", "fixture"),
            ("format", "pbf"),
            ("minzoom", "0"),
            ("maxzoom", "1"),
        ],
    )
    conn.executemany(
        "INSERT INTO tiles VALUES (?, ?, ?, ?)",
        [
            (0, 0, 0, b"x" * 100),
            (1, 0, 0, b"x" * 200),
            (1, 1, 0, b"x" * 800_000),
        ],
    )
    conn.commit()
    conn.close()

    import io
    import sys

    captured = io.StringIO()
    original = sys.stdout
    sys.stdout = captured
    try:
        code = main([str(mbtiles), "--json", "--max-tile-size", "500"])
    finally:
        sys.stdout = original
    assert code == 0

    report = json.loads(captured.getvalue())
    assert report["format"] == "mbtiles"
    assert report["total_tiles"] == 3
    assert report["total_bytes"] == 800_300
    assert len(report["oversized"]) == 1
    assert report["oversized"][0]["size"] == 800_000
