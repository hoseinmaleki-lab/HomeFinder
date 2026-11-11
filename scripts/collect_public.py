#!/usr/bin/env python3
"""Collect publicly displayed property records from specifically reviewed pages.

No logins, proxies, CAPTCHA evasion, MLS/VOW or private listing access.
Checks robots.txt before each request. Only known source-specific parsers.
Attempts every public agent/brokerage directory website; structured-data extraction is not guaranteed.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

OUT = Path("docs/data/public_listings.json")
STATUS = Path("docs/data/public_source_status.json")
UA = "HomeFinderResearchBot/1.0 (+https://github.com/hoseinmaleki-lab/HomeFinder)"
TIMEOUT = 18
# Geographic inclusion is intentionally explicit; it is not an entire-PA search.
TOWNS = {
    "ardmore", "bala cynwyd", "berwyn", "bryn mawr", "devon",
    "gladwyne", "haverford", "malvern", "merion station", "narberth",
    "newtown square", "paoli", "penn valley", "radnor", "rose valley",
    "villanova", "wayne", "wynnewood"
}
SOURCES = [
    {"name": "Bentley Homes", "url": "https://www.bentleyhomes.com/price-list/", "parser": "bentley"},
    {"name": "Robin Gordon Group", "url": "https://robingordon.com/properties/sale", "parser": "robin"},
]

def text(s):
    return " ".join(str(s or "").split())

def digits(s):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(s or ""))
    return float(m.group(0).replace(",", "")) if m else None

def allowed_by_robots(url):
    p = urlparse(url)
    rp = RobotFileParser()
    robots = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        res = requests.get(robots, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)
        if res.status_code in (401, 403):
            return False, "robots.txt access forbidden"
        if res.status_code == 404:
            return True, "robots.txt not published"
        if res.status_code != 200:
            return False, f"robots.txt unavailable ({res.status_code}); fail closed"
        rp.parse(res.text.splitlines())
        return rp.can_fetch(UA, url), "robots.txt checked"
    except requests.RequestException as exc:
        return False, f"robots.txt check failed: {type(exc).__name__}"

def fetch_page(url):
    ok, reason = allowed_by_robots(url)
    if not ok:
        raise RuntimeError(f"Not fetched: {reason}")
    res = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=TIMEOUT)
    res.raise_for_status()
    if len(res.content) > 3_000_000:
        raise RuntimeError("Page too large")
    return BeautifulSoup(res.text, "html.parser")

def parse_location(s):
    s = text(s)
    m = re.search(r"(.+?)(?:,?\s+)([A-Za-z][A-Za-z ]+),?\s+PA\s+\d{5}", s, re.I)
    if not m or text(m.group(2)).casefold() not in TOWNS:
        # Some tables collapse street and town, without a separating space.
        m = None
        for town in sorted(TOWNS, key=len, reverse=True):
            attempt = re.search(r"(.+?)\s*("+re.escape(town)+r")\s*,?\s*PA\s+\d{5}", s, re.I)
            if attempt:
                m = attempt
                break
    if not m:
        return None
    city = text(m.group(2)).title()
    if city.casefold() not in TOWNS:
        return None
    addr = text(m.group(1))
    if not addr or not re.search(r"\d", addr):
        return None
    return addr, city

def make_record(source, address, city, price, sqft, status, link, checked, beds=None, baths=None):
    if not sqft or sqft <= 3000 or city.casefold() not in TOWNS:
        return None
    if not link.startswith("https://"):
        return None
    return {"address": address, "city": city, "price": int(price) if price else None,
            "sqft": int(sqft), "beds": beds, "baths": baths,
            "status": status, "source": source, "url": link, "checked_at": checked,
            "data_origin": "public_website"}

def parse_bentley(soup, checked):
    results = []
    for row in soup.select("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 6:
            continue
        fields = [text(x.get_text(" ", strip=True)) for x in cells]
        # Schema: address, acre, floor plan, sqft, status, price, delivery.
        loc = parse_location(fields[0])
        if not loc:
            continue
        sq = digits(fields[3])
        status = fields[4].casefold()
        if "sold" in status or "available" not in status:
            continue
        price = digits(fields[5])
        link = cells[0].find("a", href=True)
        url = requests.compat.urljoin("https://www.bentleyhomes.com/price-list/", link["href"]) if link else "https://www.bentleyhomes.com/price-list/"
        item = make_record("Bentley Homes", *loc, price, sq, "Available (builder)", url, checked)
        if item:
            results.append(item)
    return results

def parse_robin(soup, checked):
    # The public /properties/sale page has cards with status, address, price, beds/baths and size.
    # Anchor to individual 'DETAILS' links where they exist, not generic site text.
    output = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = requests.compat.urljoin("https://robingordon.com/properties/sale", a["href"])
        if urlparse(href).hostname not in ("robingordon.com", "www.robingordon.com"):
            continue
        if "/properties/" not in urlparse(href).path or urlparse(href).path in ("/properties/sale", "/properties/sold", "/properties/elite"):
            continue
        parent = a
        candidate = ""
        for _ in range(5):
            parent = parent.parent
            if not parent or not getattr(parent, "get_text", None):
                break
            candidate = text(parent.get_text(" ", strip=True))
            if "Sq.Ft." in candidate and ("For Sale" in candidate or "Pending" in candidate or "Active Under Contract" in candidate):
                break
        # We only include clearly stated active "For Sale", excluding pending and under contract.
        if not candidate or "For Sale" not in candidate or "Pending" in candidate or "Active Under Contract" in candidate:
            continue
        msize = re.search(r"([\d,]+)\s*Sq\.\s*Ft\.", candidate, re.I)
        mprice = re.search(r"\$\s*([\d,]+)", candidate)
        mloc = re.search(r"([\d]+[^$]{2,100}?),\s*([A-Za-z ]+),\s*PA\s+\d{5}", candidate, re.I)
        if not msize or not mprice or not mloc:
            continue
        city = text(mloc.group(2)).title()
        if city.casefold() not in TOWNS:
            continue
        address = text(mloc.group(1))
        # Strip duplicate price text before the street (cards sometimes omit "$").
        address = re.sub(r"^(?:\d{1,3}(?:,\d{3})+\s+)+", "", address)
        address = re.sub(r"^.*?\$[\d,]+\s*", "", address)
        if not re.match(r"^\d+\s+\S+", address):
            continue
        beds = re.search(r"(\d+)\s*Beds?", candidate, re.I)
        baths = re.search(r"(\d+(?:\.\d+)?)\s*Baths?", candidate, re.I)
        record = make_record("Robin Gordon Group", address, city,
                             digits(mprice.group(1)), digits(msize.group(1)), "For Sale", href,
                             checked, int(beds.group(1)) if beds else None,
                             float(baths.group(1)) if baths else None)
        if record and (record["city"], record["address"]) not in seen:
            seen.add((record["city"], record["address"]))
            output.append(record)
    return output

def dedupe(items):
    combined = {}
    for item in items:
        key = (re.sub(r"\W+", "", item["city"].lower()),
               re.sub(r"\W+", "", item["address"].lower()))
        if key not in combined:
            combined[key] = item
        elif item["source"] != combined[key]["source"]:
            combined[key].setdefault("also_listed_by", []).append(item["source"])
    return sorted(combined.values(), key=lambda x: (x["city"], x["address"]))


def directory_sources():
    """Try every publicly listed agent/brokerage, not private discovery channels."""
    directory = json.loads(Path("docs/data/sources.json").read_text(encoding="utf-8"))
    seen = {urlparse(x["url"]).netloc.lower().removeprefix("www.") for x in SOURCES}
    result = []
    for item in directory:
        if item.get("type") != "Agent / brokerage":
            continue
        url = item.get("url", "")
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if not url.startswith("https://") or not host or host in seen:
            continue
        seen.add(host)
        result.append({"name": item["name"], "url": url, "parser": "structured"})
    return result

def structured_records(soup, source, checked):
    """Conservatively read public schema.org real-estate JSON-LD; never guess missing data."""
    results = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        stack = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            kind = node.get("@type", "")
            kinds = kind if isinstance(kind, list) else [kind]
            if not any(k in ("SingleFamilyResidence", "House", "Residence", "RealEstateListing", "Apartment", "Product") for k in kinds):
                continue
            address = node.get("address", {})
            if not isinstance(address, dict):
                continue
            street = text(address.get("streetAddress"))
            city = text(address.get("addressLocality")).title()
            region = text(address.get("addressRegion"))
            if not street or not re.match(r"^\d+\s+\S+", street) or city.casefold() not in TOWNS or region.upper() not in ("PA", "PENNSYLVANIA"):
                continue
            area = node.get("floorSize") or node.get("floorArea") or {}
            if isinstance(area, dict):
                unit = text(area.get("unitCode") or area.get("unitText")).lower()
                if unit and unit not in ("ftk", "sqft", "sq ft", "square feet", "ft2"):
                    continue
                area = area.get("value")
            sqft = digits(area)
            offers = node.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if not isinstance(offers, dict):
                offers = {}
            price = digits(offers.get("price") or node.get("price"))
            link = node.get("url") or offers.get("url") or source["url"]
            if not isinstance(link, str) or urlparse(link).netloc.lower().removeprefix("www.") != urlparse(source["url"]).netloc.lower().removeprefix("www."):
                link = source["url"]
            beds = digits(node.get("numberOfBedrooms"))
            baths = digits(node.get("numberOfBathroomsTotal"))
            record = make_record(source["name"], street, city, price, sqft, "Status unverified", link, checked, beds, baths)
            if record:
                results.append(record)
    return results

def run():
    checked = datetime.now(timezone.utc).date().isoformat()
    statuses, extracted = [], []
    for source in SOURCES + directory_sources():
        try:
            soup = fetch_page(source["url"])
            records = ({"bentley": parse_bentley, "robin": parse_robin}[source["parser"]](soup, checked) if source["parser"] != "structured" else structured_records(soup, source, checked))
            extracted.extend(records)
            statuses.append({"name": source["name"], "state": "checked", "count": len(records), "checked_at": checked})
            print(f'{source["name"]}: {len(records)} eligible properties')
        except Exception as exc:
            statuses.append({"name": source["name"], "state": "unavailable", "count": 0,
                             "reason": str(exc)[:150], "checked_at": checked})
            print(f'{source["name"]}: {exc}', file=sys.stderr)
    # Never republish stale listings as currently active after a failed run.
    unique = dedupe(extracted)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(unique, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    STATUS.write_text(json.dumps({"checked_at": checked, "source_count": len(statuses),
                                  "listing_count": len(unique), "sources": statuses}, indent=2) + "\n",
                      encoding="utf-8")
    print(f"Saved {len(unique)} public-source listings")
    return 0 if any(x["state"] == "checked" for x in statuses) else 1

if __name__ == "__main__":
    sys.exit(run())
