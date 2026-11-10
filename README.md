# HomeFinder — Philadelphia Main Line

A public-facing, searchable home discovery dashboard for homes **over 3,000 sq ft** on the Philadelphia Main Line. Source code is in a private repository; GitHub Pages, if enabled, may be public.

## Status
This is an initial deployment scaffold. The research links are discovery resources, **not verified current listings**. No unauthorized scraping or access to private MLS data is enabled.

## Site
The static site is in `docs/`. To publish, open **Settings → Pages**, choose **Deploy from a branch**, branch **main**, folder **/docs**. Confirm that the site can be public before enabling it.

## Update listings
Add verified, permitted public listings to `docs/data/listings.json`. Each entry supports `address`, `city`, `price`, `sqft`, `beds`, `baths`, `url`, `source`, `status`, `checked_at`. Do not publish confidential office-exclusive or agent-only data.

## Research
The directory in `docs/data/sources.json` provides starting points for builder, brokerage, and private-listing inquiries. These sites have different permissions and policies. Verify sources and listing freshness before treating any property as available.

## Roadmap
1. Validate sources and add authorized public feeds.
2. Add source-specific parsers and deduplication.
3. Run scheduled collection in GitHub Actions only where expressly permitted.
4. Add user alerts and manual agent-supplied leads (private data should not go into Pages).
