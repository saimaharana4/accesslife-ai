# Curated source manifest

The bootstrap catalogue has three venues per city. Coordinates are approximate venue positions, not accessible entrance coordinates. Known facts are narrow original paraphrases with official source links; no full source page or proprietary Qloo response is redistributed.

| City | Venue | Source | Recorded feature summaries |
|---|---|---|---:|
| london | British Museum | [Official venue page](https://www.britishmuseum.org/visit/accessibility-museum) | 3 |
| london | National Gallery | [Official venue page](https://www.nationalgallery.org.uk/visiting/access) | 1 |
| london | Tate Modern | [Official venue page](https://www.tate.org.uk/visit/tate-modern) | 0 |
| new-york | The Metropolitan Museum of Art | [Official venue page](https://www.metmuseum.org/visit-guides/accessibility) | 1 |
| new-york | Museum of Modern Art | [Official venue page](https://www.moma.org/visit/accessibility/social-access-guide) | 1 |
| new-york | Whitney Museum of American Art | [Official venue page](https://whitney.org/visit/access) | 0 |
| paris | Musée du Louvre | [Official venue page](https://www.louvre.fr/en/visit/accessibility) | 0 |
| paris | Musée d’Orsay | [Official venue page](https://www.musee-orsay.fr/en/articles/accessibility-services-296252) | 1 |
| paris | Musée de l’Orangerie | [Official venue page](https://www.musee-orangerie.fr/en/vous-etes/groupes-orangerie/accessibility-and-health-care-sector) | 0 |
| berlin | Jewish Museum Berlin | [Official venue page](https://www.jmberlin.de/en/accessibility) | 2 |
| berlin | Lebenswelten Bistro | [Official venue page](https://www.humboldtforum.org/en/programm/dauerangebot/food-and-drink/lebenswelten-bistro-23376/) | 0 |
| berlin | Humboldt Forum | [Official venue page](https://www.humboldtforum.org/en/visit/) | 0 |
| chicago | Field Museum | [Official venue page](https://www.fieldmuseum.org/page/visi/accessibility) | 2 |
| chicago | Museum of Contemporary Art Chicago | [Official venue page](https://mcachicago.org/visit/faq/) | 1 |
| chicago | Art Institute of Chicago | [Official venue page](https://www.artic.edu/visit/accessibility) | 0 |

Retrieval date: 24 October 2026. Source-update dates are unknown unless explicitly recorded. Some pages block automated retrieval; this does not establish current access. Feature summaries include limited lift statements and unknown facts, never a blanket venue/journey guarantee. No city is coverage-complete.

Run `docker compose --profile tools run --rm ingest` to index the 12 original summaries and approximate coordinates. The command is idempotent. CPU MiniLM uses 384-dimensional normalized embeddings, a pinned revision and hybrid lexical/vector retrieval. Empty/unavailable retrieval remains explicit. The five-city retrieval smoke checks query/attribution plumbing, not held-out recall or real-world route coverage.

Source pages retain their own copyright. The project publishes its own short factual summaries and links; do not infer permission to bulk mirror those pages. OSM/OpenFreeMap retain their map/data terms and attribution. Before admitting additional material, record permission, provenance, update/freshness policy and transformation revision. Qloo data never enters this corpus.
