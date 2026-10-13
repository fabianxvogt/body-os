# Vendored third-party files

The dashboard makes no external requests, so its one dependency is copied here.

| File | Source | Version | SHA-256 | Licence |
|---|---|---|---|---|
| `echarts.min.js` | https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js | Apache ECharts 5.5.1 | `e84270bd0cd5bdf60fefc26d00c2a391cb2e81f4d26a7a9ee16185a54773a3cf` | Apache-2.0 ([ECHARTS-LICENSE](ECHARTS-LICENSE), [ECHARTS-NOTICE](ECHARTS-NOTICE)) |

Update: download the new `dist/echarts.min.js`, `LICENSE` and `NOTICE` from the same npm package, replace
the files, and record the new version and `shasum -a 256 echarts.min.js` here (a test checks the hash).
