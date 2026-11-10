# Public-source property collectors

This system is separate from Bright MLS. It fetches publicly displayed information only from explicitly reviewed source pages. The script checks robots.txt, doesn't log in, doesn't bypass blocks, and doesn't attempt to retrieve private or early-access listings.

## Sources currently implemented
- Bentley Homes public price list: https://www.bentleyhomes.com/price-list/ — table parser. Only rows explicitly marked Available; homes over 3,000 sq ft in configured Main Line communities.
- Robin Gordon Group public For Sale page: https://robingordon.com/properties/sale — conservative public property card parser, only those clearly marked For Sale.

**These are the first two implemented collectors, not all 57 research links.** Many of the 57 sources are agents, contact forms, records or discovery channels with no suitable public listing feed. Each additional collector needs specific review and tests. If robots policy blocks access or HTML structure differs, source is shown unavailable and no records are fabricated.

## Run
`pip install -r requirements-public.txt`
`python scripts/collect_public.py`

Data is saved to `docs/data/public_listings.json`, status to `docs/data/public_source_status.json`. GitHub Action **Collect public property pages** runs twice daily and supports manual workflow dispatch.

The website combines these public records with records from authorized feeds in `docs/data/listings.json`, deduplicates by address+city, and shows cross-posting source names.

## Important limitations
- Published page information is not equivalent to verified MLS inventory. Availability and prices require agent confirmation.
- The two parsers are conservative. They can return zero listings if site content is script-rendered or a site changes its markup.
- Any source that denies automated access through robots.txt is skipped.
- Homes with unverified size are excluded; filter uses >3,000 sq ft.
- Stale datasets may remain displayed if deployment or refresh fails; check the **checked** date for each property.
- A public site must not contain private, office-exclusive, VOW or personally provided confidential listings.
- This code is for a personal research prototype, not a bulk data redistribution authorization.
