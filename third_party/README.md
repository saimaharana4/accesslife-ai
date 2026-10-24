# Model redistribution

The API image includes CPU ONNX weights, tokenizer and model card for
[`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2),
revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`. Its model card declares Apache License 2.0.
The unchanged model card is bundled in the image cache; [the Apache license](MiniLM-LICENSE.txt)
is included here and in `/opt/models/MiniLM-APACHE-2.0-LICENSE`. Weights are downloaded
from the original publisher during image build and are not committed to Git.

MapLibre uses the [OpenFreeMap Liberty style](https://openfreemap.org/quick_start/).
Keep its map attribution visible. OSM data retains ODbL attribution and rights;
venue source pages retain their own copyright. Original short factual summaries
and source links are recorded in the backend catalogue. Qloo payloads stay in a
private database cache with a one-hour validity TTL and periodic expiry cleanup; they are never published as a dataset.
