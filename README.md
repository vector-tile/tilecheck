# tilecheck

Audit [PMTiles](https://docs.protomaps.com/pmtiles/) and MBTiles archives for the things that actually hurt browser rendering and CDN performance: oversized tiles, lopsided zoom-level distributions, and missing or wrong metadata.

Built and maintained by [vector-tile.com](https://www.vector-tile.com) — the vector tile pipeline & caching reference.

## Install

Install directly from this repository:

```sh
pip install git+https://github.com/vector-tile/tilecheck.git
```

Or use [pipx](https://pipx.pypa.io/) to keep it isolated from your system Python:

```sh
pipx install git+https://github.com/vector-tile/tilecheck.git
```

> A PyPI release is planned. Until then, install from the Git URL above.

## Usage

```sh
tilecheck path/to/tiles.pmtiles
```

```text
path/to/tiles.pmtiles
  format: pmtiles
  tile type: mvt   zoom range: 0–14   compression: gzip
  layers (3): roads, buildings, places

  total tiles: 184,213
  total bytes: 412.7 MB

  zoom       count         avg         min         max  largest tile
  ----  ----------         ---         ---         ---  --------------------
     0           1     1.2 KB     1.2 KB     1.2 KB    0/0/0
     1           4     2.3 KB     1.8 KB     2.9 KB    1/1/0
     ...
    13      45,621    18.4 KB     1.1 KB   612.0 KB   13/4319/2890
    14     128,452    24.8 KB     0.8 KB     1.4 MB   14/8638/5780

  3 oversized tile(s) (> 500.0 KB):
    14/8638/5780   1.4 MB
    14/8639/5780   980.0 KB
    13/4319/2890   612.0 KB
```

### Common workflows

Set a custom oversized threshold (in KB):

```sh
tilecheck tiles.pmtiles --max-tile-size 250
```

Emit machine-readable JSON (good for CI dashboards):

```sh
tilecheck tiles.pmtiles --json > report.json
```

Fail the build when any tile blows past your limit:

```sh
tilecheck tiles.pmtiles --max-tile-size 500 --exit-on-oversized
```

Works on MBTiles too:

```sh
tilecheck planet.mbtiles
```

## Why it exists

Tippecanoe and friends will happily generate a tile that's perfectly valid but 2 MB heavy — your map looks fine on the dev's laptop, then chokes on a $30 phone in the field. Edge caches will store and serve that tile regardless. `tilecheck` gives you a 5-second answer to "did my last build introduce any tiles that will tank performance?", and a CI-friendly exit code to make sure the answer stays no.

For deeper reading on tile pipelines, caching strategies, and styling sync, see [vector-tile.com](https://www.vector-tile.com).

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0    | Report rendered successfully. |
| 1    | Bad input (file missing, unsupported format). |
| 2    | `--exit-on-oversized` was set and at least one tile exceeded the threshold. |

## Development

```sh
git clone https://github.com/vector-tile/tilecheck.git
cd tilecheck
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## License

MIT — see [LICENSE](LICENSE).
