"""Tile-source readers that yield a uniform stream of (z, x, y, size) tuples."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from pmtiles.reader import (
    MmapSource,
    Reader,
    deserialize_directory,
    tileid_to_zxy,
)


@dataclass
class TileStream:
    """Iterable view of a tile archive plus its metadata."""

    format: str
    path: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    header: dict[str, Any] = field(default_factory=dict)
    tiles: Iterator[tuple[int, int, int, int]] = field(default_factory=iter)


def open_archive(path: Path) -> TileStream:
    """Detect the archive format from the file extension and open it."""
    suffix = path.suffix.lower()
    if suffix == ".pmtiles":
        return _open_pmtiles(path)
    if suffix in {".mbtiles", ".sqlite", ".db"}:
        return _open_mbtiles(path)
    raise ValueError(
        f"Unsupported file type {suffix!r}. Expected .pmtiles or .mbtiles."
    )


def _open_pmtiles(path: Path) -> TileStream:
    fh = path.open("rb")
    source = MmapSource(fh)
    reader = Reader(source)
    header = reader.header()
    metadata = reader.metadata() or {}

    def iter_tiles() -> Iterator[tuple[int, int, int, int]]:
        try:
            yield from _walk_pmtiles_dir(
                source, header, header["root_offset"], header["root_length"]
            )
        finally:
            fh.close()

    return TileStream(
        format="pmtiles",
        path=path,
        metadata=metadata,
        header=_normalize_pmtiles_header(header),
        tiles=iter_tiles(),
    )


def _normalize_pmtiles_header(header: dict[str, Any]) -> dict[str, Any]:
    """Convert PMTiles enum values to friendly strings and JSON-safe primitives."""
    out: dict[str, Any] = {}
    for key, value in header.items():
        out[key] = _enum_value(value)
    tile_type = _enum_value(header.get("tile_type"))
    if tile_type is not None:
        out["tile_type_name"] = _PMTILES_TILE_TYPE.get(int(tile_type), str(tile_type))
    compression = _enum_value(header.get("tile_compression"))
    if compression is not None:
        out["tile_compression_name"] = _PMTILES_COMPRESSION.get(
            int(compression), str(compression)
        )
    return out


def _enum_value(value: Any) -> Any:
    """Return the underlying value of an Enum, leaving primitives untouched."""
    if value is None:
        return None
    inner = getattr(value, "value", None)
    if inner is not None and not isinstance(value, (int, float, str, bool, bytes)):
        return inner
    return value


_PMTILES_TILE_TYPE = {
    0: "unknown",
    1: "mvt",
    2: "png",
    3: "jpeg",
    4: "webp",
    5: "avif",
}

_PMTILES_COMPRESSION = {
    0: "unknown",
    1: "none",
    2: "gzip",
    3: "brotli",
    4: "zstd",
}


def _walk_pmtiles_dir(
    get_bytes,
    header: dict[str, Any],
    dir_offset: int,
    dir_length: int,
) -> Iterator[tuple[int, int, int, int]]:
    """Walk PMTiles directories yielding (z, x, y, length) without reading tile payloads."""
    entries = deserialize_directory(get_bytes(dir_offset, dir_length))
    for entry in entries:
        if entry.run_length > 0:
            for i in range(entry.run_length):
                z, x, y = tileid_to_zxy(entry.tile_id + i)
                yield z, x, y, entry.length
        else:
            yield from _walk_pmtiles_dir(
                get_bytes,
                header,
                header["leaf_directory_offset"] + entry.offset,
                entry.length,
            )


def _open_mbtiles(path: Path) -> TileStream:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    metadata: dict[str, Any] = {}
    for row in conn.execute("SELECT name, value FROM metadata"):
        key, value = row["name"], row["value"]
        if key == "json":
            try:
                metadata["json"] = json.loads(value)
            except json.JSONDecodeError:
                metadata["json"] = value
        else:
            metadata[key] = value

    header: dict[str, Any] = {}
    if "format" in metadata:
        header["tile_type_name"] = metadata["format"]
    if "minzoom" in metadata:
        try:
            header["min_zoom"] = int(metadata["minzoom"])
        except (TypeError, ValueError):
            pass
    if "maxzoom" in metadata:
        try:
            header["max_zoom"] = int(metadata["maxzoom"])
        except (TypeError, ValueError):
            pass

    def iter_tiles() -> Iterator[tuple[int, int, int, int]]:
        try:
            cursor = conn.execute(
                "SELECT zoom_level, tile_column, tile_row, "
                "LENGTH(tile_data) AS size FROM tiles"
            )
            for row in cursor:
                z = int(row["zoom_level"])
                x = int(row["tile_column"])
                # MBTiles uses TMS y; flip to XYZ for consistent reporting.
                tms_y = int(row["tile_row"])
                y = (1 << z) - 1 - tms_y
                yield z, x, y, int(row["size"])
        finally:
            conn.close()

    return TileStream(
        format="mbtiles",
        path=path,
        metadata=metadata,
        header=header,
        tiles=iter_tiles(),
    )
