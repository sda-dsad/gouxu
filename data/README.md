# Local data

The only bundled dataset is `fixtures/layout.synthetic.json`: 336 synthetic requests and 28 invented products.
Downloaded JSONL, prepared Parquet, SQLite state, uploads and exports are local-only and ignored by Git.
Docker stores state in the named `state` volume and mounts `data/processed` read-only.
For optional real data, follow [data sources](../docs/03_DATA_SOURCES.md).
