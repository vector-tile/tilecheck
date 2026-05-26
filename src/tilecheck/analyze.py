"""Aggregate tile streams into a structured health report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class ZoomStats:
    zoom: int
    count: int = 0
    total_bytes: int = 0
    min_bytes: int = 0
    max_bytes: int = 0
    max_tile: tuple[int, int, int] | None = None  # (z, x, y) of largest tile

    @property
    def avg_bytes(self) -> float:
        return self.total_bytes / self.count if self.count else 0.0


@dataclass
class OversizedTile:
    z: int
    x: int
    y: int
    size: int


@dataclass
class Report:
    format: str
    path: str
    header: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    zooms: list[ZoomStats] = field(default_factory=list)
    oversized: list[OversizedTile] = field(default_factory=list)
    total_tiles: int = 0
    total_bytes: int = 0
    oversized_threshold: int = 0


def analyze(
    stream: Iterable[tuple[int, int, int, int]],
    *,
    oversized_threshold: int,
    oversized_limit: int = 20,
) -> tuple[list[ZoomStats], list[OversizedTile], int, int]:
    """Walk a tile stream and produce per-zoom stats plus an oversized list.

    `oversized_threshold` is in bytes. Tiles strictly larger than that are
    collected up to `oversized_limit`, sorted by size descending.
    """
    by_zoom: dict[int, ZoomStats] = {}
    oversized: list[OversizedTile] = []
    total_tiles = 0
    total_bytes = 0

    for z, x, y, size in stream:
        total_tiles += 1
        total_bytes += size
        stats = by_zoom.get(z)
        if stats is None:
            stats = ZoomStats(zoom=z, count=1, total_bytes=size,
                              min_bytes=size, max_bytes=size, max_tile=(z, x, y))
            by_zoom[z] = stats
        else:
            stats.count += 1
            stats.total_bytes += size
            if size < stats.min_bytes:
                stats.min_bytes = size
            if size > stats.max_bytes:
                stats.max_bytes = size
                stats.max_tile = (z, x, y)
        if oversized_threshold > 0 and size > oversized_threshold:
            oversized.append(OversizedTile(z=z, x=x, y=y, size=size))

    oversized.sort(key=lambda t: t.size, reverse=True)
    oversized = oversized[:oversized_limit]
    zooms = sorted(by_zoom.values(), key=lambda s: s.zoom)
    return zooms, oversized, total_tiles, total_bytes
