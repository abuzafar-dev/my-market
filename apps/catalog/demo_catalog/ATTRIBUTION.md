# Demo catalogue — sources and licences

`products.json` and `images/` are used only by `manage.py seed_demo`
(`SEED_DEMO=True`). A real shop never sees them.

The photos are **not** covered by the project's own licence. Each keeps the
licence of its source, listed per product in `products.json` (`source`,
`license`):

- **93 packaged products** — photos and barcodes from
  [Open Food Facts](https://world.openfoodfacts.org), products sold in
  Uzbekistan. Images are licensed
  [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); the
  contributors of each photo are listed on the product page given in `source`.
- **7 fruits and vegetables** (sold by kg) — from
  [Wikimedia Commons](https://commons.wikimedia.org); licence and author per
  file in `products.json` (CC0, public domain, CC BY 2.0 or CC BY-SA 3.0).

Changes made: resized to at most 480 px and re-encoded as JPEG (metadata
removed). Product names were shortened or written in Uzbek; prices are
invented, typical shop prices in so'm — not real supplier data.

Selected and downloaded on 2026-11-25.
