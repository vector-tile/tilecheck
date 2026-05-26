"""Human and machine-readable renderers for a Report."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from tilecheck.analyze import Report


def to_json(report: Report) -> str:
    return json.dumps(asdict(report), indent=2, default=_default)


def _default(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def to_text(report: Report, *, use_color: bool = True) -> str:
    c = _Colors(enabled=use_color)
    out: list[str] = []
    out.append(f"{c.bold}{report.path}{c.reset}")
    out.append(f"  format: {report.format}")

    header = report.header
    if header:
        tile_type = header.get("tile_type_name", "?")
        compression = header.get("tile_compression_name")
        zoom_range = f"{header.get('min_zoom', '?')}–{header.get('max_zoom', '?')}"
        line = f"  tile type: {tile_type}   zoom range: {zoom_range}"
        if compression:
            line += f"   compression: {compression}"
        out.append(line)

    layers = _layer_names(report.metadata)
    if layers:
        out.append(f"  layers ({len(layers)}): {', '.join(layers)}")

    out.append("")
    out.append(f"  total tiles: {report.total_tiles:,}")
    out.append(f"  total bytes: {_human_bytes(report.total_bytes)}")
    out.append("")

    if report.zooms:
        out.append(
            f"  {'zoom':>4}  {'count':>10}  {'avg':>10}  {'min':>10}  {'max':>10}  largest tile"
        )
        out.append(f"  {'-' * 4}  {'-' * 10}  {'-' * 10}  {'-' * 10}  {'-' * 10}  {'-' * 20}")
        for z in report.zooms:
            largest = ""
            if z.max_tile is not None:
                tz, tx, ty = z.max_tile
                largest = f"{tz}/{tx}/{ty}"
            color = ""
            reset = ""
            if report.oversized_threshold and z.max_bytes > report.oversized_threshold:
                color = c.yellow
                reset = c.reset
            out.append(
                f"  {z.zoom:>4}  {z.count:>10,}  "
                f"{_human_bytes(int(z.avg_bytes)):>10}  "
                f"{_human_bytes(z.min_bytes):>10}  "
                f"{color}{_human_bytes(z.max_bytes):>10}{reset}  {largest}"
            )

    if report.oversized:
        out.append("")
        out.append(
            f"  {c.yellow}{len(report.oversized)} oversized tile(s) "
            f"(> {_human_bytes(report.oversized_threshold)}):{c.reset}"
        )
        for t in report.oversized:
            out.append(
                f"    {t.z}/{t.x}/{t.y}  {_human_bytes(t.size)}"
            )
    elif report.oversized_threshold:
        out.append("")
        out.append(
            f"  {c.green}no tiles exceed "
            f"{_human_bytes(report.oversized_threshold)}{c.reset}"
        )

    return "\n".join(out) + "\n"


def _layer_names(metadata: dict[str, Any]) -> list[str]:
    vector_layers: list[Any] = []
    if isinstance(metadata.get("vector_layers"), list):
        vector_layers = metadata["vector_layers"]
    elif isinstance(metadata.get("json"), dict):
        inner = metadata["json"].get("vector_layers")
        if isinstance(inner, list):
            vector_layers = inner
    names: list[str] = []
    for layer in vector_layers:
        if isinstance(layer, dict) and "id" in layer:
            names.append(str(layer["id"]))
    return names


def _human_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n_f = n / 1024
        if n_f < 1024 or unit == "GB":
            return f"{n_f:.1f} {unit}"
        n = int(n_f)
    return f"{n} B"


class _Colors:
    def __init__(self, enabled: bool) -> None:
        if enabled:
            self.bold = "\033[1m"
            self.yellow = "\033[33m"
            self.green = "\033[32m"
            self.reset = "\033[0m"
        else:
            self.bold = self.yellow = self.green = self.reset = ""


