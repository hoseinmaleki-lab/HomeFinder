# Connecting authorized HomeFinder listing feeds

## What works now
The scheduled action **Sync approved listing feeds** runs every 6 hours and on demand.
It reads approved JSON/CSV listing feeds, keeps homes **over 3,000 sq ft**, filters out sold/withdrawn properties, combines duplicates and publishes the results into the website's sortable property table.

**No listings are fabricated.** The job does not scrape Zillow, Redfin, MLS portals or private brokerage sites. It only fetches feed URLs you are authorized to use.

## Configure the first source
1. Obtain express permission to fetch **and publicly display** listing data from a brokerage, builder, or data provider. Do not use private-exclusive or VOW feeds on this public website.
2. The authorized source should publish a JSON or CSV feed over HTTPS with publicly shareable listing URLs.
3. Go to GitHub → HomeFinder → Settings → Secrets and variables → Actions → New repository secret.
4. Set the name to `HOMEFINDER_FEEDS_JSON`.
5. Set its value to a JSON array of approved feeds such as:
```json
[
  {"name":"My authorized brokerage feed","url":"https://example.com/feed.json","format":"json"},
  {"name":"My approved builder feed","url":"https://example.com/feed.csv","format":"csv"}
]
```
URLs above are **examples only**, not live feeds.
6. Open Actions → **Sync approved listing feeds** → Run workflow.
7. Check the workflow logs. After a successful run, refresh GitHub Pages.

## Feed schema
JSON can be a list or an object containing a `listings` / `properties` / `results` / `value` list. CSV can use the same columns.

Required: `city`, `sqft` (>3000), `url` (HTTPS). Recommended: `address`, `price`, `beds`, `baths`, `status`, `listing_id`, `brokerage`. Supported aliases include RESO fields such as `City`, `ListPrice`, `LivingArea`, `BedroomsTotal`, `BathroomsTotalInteger`, and `StandardStatus`.

Example authorized public record (illustrative, **not** a real listing):
```json
[{"address":"Example Rd","city":"Haverford","price":1500000,"sqft":4100,"beds":4,"baths":3,"status":"Active","url":"https://example.com/listing/123","listing_id":"123"}]
```

## Data-source caveats
- **Bright MLS:** Official RESO API information is at https://brightmls.portal.swaggerhub.com/. The public display license and applicable rules must be approved first. Even if credentials are available, IDX rights are not automatically granted to a consumer-owned website.
- **Zillow Bridge:** https://www.zillowgroup.com/developers/api/mls-broker-data/mls-listings/ describes access-controlled MLS/broker listing APIs. Access and rights depend on the MLS.
- **Agents / private exclusives:** Ask for permission to receive a public-approved feed of properties that may be displayed. Keep genuinely private leads outside GitHub Pages.
- **Never** commit API keys, private-agent lists or confidential data. GitHub Pages is public.

## Operational notes
- If no feed is configured, the workflow leaves the current inventory alone.
- If all feeds fail, the workflow fails and retains the last published inventory.
- If a feed returns zero eligible listings, the workflow retains old inventory to avoid accidental outages. **This means stale properties can remain published**; check dated records and confirm all listings directly.
- Feed errors are recorded only when at least one feed succeeds. Listings without a stable ID are deduplicated by address and town; no attempt is made to merge different units at one property.
- This adapter targets public-approved syndication data. An official RESO/IDX integration needs additional compliance handling (broker attribution, permitted fields, change/deletion propagation, and display requirements) before use.

## Next engineering steps
Add source-specific adapters for approved partners, remove delisted records when reliable full snapshots become available, implement stale-record badges, and ensure the scope of towns is controlled. No official MLS integration is authorized yet.
