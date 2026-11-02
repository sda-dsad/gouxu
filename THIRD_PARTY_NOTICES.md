# Third-party notices

The project license covers original application code, documentation and self-created synthetic fixtures. Dependencies retain their own licenses. This source distribution does not vendor dependency binaries, fonts, real datasets or upstream source repositories.

Direct frontend dependencies are Vue, Pinia and Three.js (MIT); development uses Vite, TypeScript, vue-tsc and the types listed in package-lock.json. Python dependencies include FastAPI, Uvicorn, DuckDB, PyArrow, HTTPX and jsonschema. Refer to their installed distributions for full license and attribution texts, including transitive dependencies.

`dependency-licenses.json` records the license identifiers available in the frontend lockfile and the installed Python package metadata at assembly time; missing metadata is marked explicitly. It is an inventory, not a replacement for upstream notices. Docker images carry their own operating-system and runtime component notices.

KuaiSearch is a separate upstream dataset/project, not bundled or relicensed here. Its previously recorded HF MIT metadata and paper v4 Appendix G CC BY 4.0 statement remain unresolved. See [data sources](docs/03_DATA_SOURCES.md). No upstream endorsement is implied.

Project MIT text: [Open Source Initiative](https://opensource.org/license/mit).
CI references: [checkout](https://github.com/actions/checkout), [setup-node](https://github.com/actions/setup-node), [setup-python](https://github.com/actions/setup-python).
