# Vendored third-party files

The dashboard makes no external requests, so its dependencies are copied here.

| File | Source | Version | SHA-256 | Licence |
|---|---|---|---|---|
| `echarts.min.js` | https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js | Apache ECharts 5.5.1 | `e84270bd0cd5bdf60fefc26d00c2a391cb2e81f4d26a7a9ee16185a54773a3cf` | Apache-2.0 ([ECHARTS-LICENSE](ECHARTS-LICENSE), [ECHARTS-NOTICE](ECHARTS-NOTICE)) |
| `qrcode.js` | https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.js | qrcode-generator 1.4.4 (Kazuhiko Arase), used only by the loopback-only `/devices` page | `18ae399f81182bc9de916e9c77b195df20cc58d6f2d55a62b085a299f1bf1780` | MIT ([QRCODE-LICENSE](QRCODE-LICENSE)) |

Update: download the new `dist/echarts.min.js`, `LICENSE` and `NOTICE` from the same npm package, replace
the files, and record the new version and `shasum -a 256 echarts.min.js` here (a test checks the hash). Same for
`qrcode.js` (the npm package ships no separate LICENSE file; the MIT notice is in its header).
