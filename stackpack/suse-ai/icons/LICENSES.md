# Icon provenance

The release uses the original Apache-2.0 SVGs documented in
[outline/LICENSES.md](outline/LICENSES.md) for category menus and owned
model/agent/GPU components. Their drawing grid is 40×40; intrinsic dimensions are
16×16 to fit the native navigation header. Role icons now also apply to AI-tagged
OpenTelemetry services and instances through icon-only presentations. The user
explicitly approved this shared visual change on 2026-11-09.

The StackPack catalog logo is the original SUSE PNG restored byte-for-byte from the
previous release asset (`b0d5867:stackpack/suse-ai/resources/logo.png`).
The SUSE AI menu group uses the chameleon-only `menu.png` supplied by the user on
2026-11-06. `suse-logo.svg` embeds that 128×128 PNG unchanged, with 16×16 intrinsic
navigation dimensions. The embedded PNG's SHA-256 is
`eea9aaa58e65a96cf724853011e1aeee6835f602a9c5d17541b16dcbfc439b5b`.
SUSE branding remains subject to SUSE's trademark rights; no Apache licence is
asserted for either asset.

The product SVGs in `products/` are restored from the published GitHub `v3.0.0`
tag (`03a8701a0289525a2038d0c2653c2e2068058260`), at the same repository paths.
Their original viewBoxes and drawings are retained inside a light-green rounded
tile so dark artwork stays visible on both light pages and dark headers. The
outer asset uses 16×16 intrinsic dimensions and a 40×40 grid. They identify Elasticsearch, KServe,
Kubeflow Model Registry/Pipelines, LiteLLM, Milvus, MLflow, Ollama, Open WebUI,
OpenSearch, Qdrant and vLLM. Vendor names and logos remain their respective
owners' trademarks; no additional licence or endorsement is asserted here.
mcpo uses the original Apache-2.0 tool glyph instead of a legacy stock PNG.

The legacy stock-style PNGs remain removed. ComponentType icon fields were not
changed. The historical spike sketches remain documented in
[experiments/component-model/icons/LICENSES.md](../../../experiments/component-model/icons/LICENSES.md).
