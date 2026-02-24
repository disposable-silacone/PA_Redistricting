# Data directory

Place the following files here (they are not committed; see root `.gitignore`):

- **block_level_data.gpkg** — Block-level geography, population, and vote totals. Must have columns: `GEOID20`, `block_pop`, `dem_block`, `rep_block`, `geometry`, and tract ID (`TRACT_GEOID20` or `STATEFP20` + `COUNTYFP20` + `TRACTCE20`).
- **tl_2020_42_cd116.shp** (and `.shx`, `.dbf`, `.prj`, etc.) — Census TIGER 2020 PA congressional districts (116th Congress). District column: `CD116FP`.
- **tl_2020_42_cd113.shp** (and sidecars) — Optional; for CD113 map. District column: `CD113FP`.

Census TIGER shapefiles: [Census Bureau TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html). Block-level data must be built or obtained separately (e.g. from a state/county or merged Census + election data).
