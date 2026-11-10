#!/usr/bin/env python3
"""Aggregate APPROVED public-listing feeds into HomeFinder.

Configure HOMEFINDER_FEEDS_JSON as a GitHub Actions secret containing a JSON array:
[{"name":"Authorized brokerage","url":"https://example.com/approved-listings.json","format":"json"}]

Only use feeds for which you have express republication rights. All output in docs/
is public on GitHub Pages. Never include private/office-exclusive or VOW-only data.
"""
import csv
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

OUT = Path("docs/data/listings.json")
STATUS = Path("docs/data/feeds_status.json")
ALLOWED = {"active", "coming soon", "pending", "for sale", "new construction"}
MAX_SIZE = 8_000_000
UA = "HomeFinder/1.0 (+authorized-feed-import; no crawling)"
FIELDS = ("address", "city", "price", "sqft", "beds", "baths", "url", "source", "status", "checked_at", "listing_id", "brokerage")

def number(raw):
    if raw is None or raw == "":
        return None
    try:
        return float(re.sub(r"[^0-9.\-]", "", str(raw)))
    except ValueError:
        return None

def approved_url(url):
    parsed = urlparse(str(url))
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password

def normalize(record, name, checked):
    if not isinstance(record, dict):
        return None
    def get(*keys):
        return next((record[k] for k in keys if k in record and record[k] not in (None, "")), None)
    sq = number(get("sqft", "living_area", "LivingArea", "AboveGradeFinishedArea"))
    if sq is None or sq <= 3000:
        return None
    url = get("url", "listing_url", "public_url")
    if not approved_url(url):
        return None
    status = str(get("status", "StandardStatus") or "Active").strip()
    if status.casefold() not in ALLOWED:
        return None
    address = get("address", "UnparsedAddress", "street_address")
    city = get("city", "City")
    if not city:
        return None
    result = {
        "address":str(address or "Address withheld").strip(),
        "city":str(city).strip(),
        "price":number(get("price", "ListPrice")),
        "sqft":round(sq),
        "beds":number(get("beds", "BedroomsTotal")),
        "baths":number(get("baths", "BathroomsTotalInteger")),
        "url":str(url).strip(),
        "source":name,
        "status":status,
        "checked_at":checked,
        "listing_id":str(get("listing_id", "ListingKey", "ListingId") or "").strip(),
        "brokerage":str(get("brokerage", "ListOfficeName") or "").strip(),
    }
    if not result["address"] or result["address"].lower()=="none":
        result["address"]="Address withheld"
    return result

def fetch_feed(feed):
    url=feed.get("url","")
    if not approved_url(url):
        raise ValueError("Feed URL must be an absolute HTTPS URL")
    request=Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/csv,text/plain"})
    with urlopen(request, timeout=25) as response:
        data=response.read(MAX_SIZE+1)
        if len(data)>MAX_SIZE:
            raise ValueError("Feed exceeded 8MB limit")
        charset=response.headers.get_content_charset() or "utf-8"
    content=data.decode(charset)
    fmt=feed.get("format","json").lower()
    if fmt=="csv":
        return list(csv.DictReader(io.StringIO(content)))
    if fmt=="json":
        body=json.loads(content)
        if isinstance(body,list):
            return body
        if isinstance(body,dict):
            for key in ("listings","properties","results","value"):
                if isinstance(body.get(key),list):
                    return body[key]
        raise ValueError("JSON feed must be a list or object with listings/properties/results/value list")
    raise ValueError("Unsupported feed format; use json or csv")

def key_for(item):
    # Prefer an authoritative listing ID; otherwise normalized address+town.
    lid=item.get("listing_id","").strip().casefold()
    if lid:
        return "id:"+lid
    address=re.sub(r"[^a-z0-9]","",item["address"].casefold())
    city=re.sub(r"[^a-z0-9]","",item["city"].casefold())
    return "property:"+city+":"+address if address and address!="addresswithheld" else "url:"+item["url"].casefold()

def sync(config, dry_run=False):
    if not isinstance(config,list):
        raise ValueError("HOMEFINDER_FEEDS_JSON must contain a JSON array")
    if not config:
        print("No approved feeds configured. Existing published inventory left untouched.")
        return 0
    today=datetime.now(timezone.utc).date().isoformat()
    by_key={}
    stats=[]
    success=0
    for feed in config:
        name=str(feed.get("name","")).strip() if isinstance(feed,dict) else ""
        if not name:
            raise ValueError("Every feed requires a name")
        try:
            records=fetch_feed(feed)
            accepted=0
            for record in records:
                item=normalize(record,name,today)
                if item is None:
                    continue
                key=key_for(item)
                if key not in by_key:
                    by_key[key]=item
                else:
                    # Preserve all known sources for cross-posted listings.
                    seen=by_key[key].setdefault("also_listed_by",[])
                    if name!=by_key[key]["source"] and name not in seen:
                        seen.append(name)
                accepted+=1
            success+=1
            stats.append({"source":name,"status":"ok","received":len(records),"eligible":accepted,"checked_at":today})
        except Exception as error:
            print(f"Feed {name} failed: {error}",file=sys.stderr)
            stats.append({"source":name,"status":"error","message":str(error)[:180],"checked_at":today})
    # Never erase a previously valid published dataset due to a bad feed or an empty outage response.
    if not success:
        print("All feeds failed; retaining previous published data.",file=sys.stderr)
        return 1
    if not by_key:
        print("No eligible records returned; retaining previous published data to avoid an accidental wipe.")
        return 0
    records=sorted(by_key.values(),key=lambda x:(x["city"].casefold(),x["address"].casefold()))
    if not dry_run:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(records,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        STATUS.write_text(json.dumps({"checked_at":today,"configured_feeds":len(config),"successful_feeds":success,"sources":stats},indent=2)+"\n",encoding="utf-8")
    print(f"Published {len(records)} unique records from {success}/{len(config)} responding feeds")
    return 0

if __name__=="__main__":
    try:
        cfg=json.loads(os.environ.get("HOMEFINDER_FEEDS_JSON","[]"))
        sys.exit(sync(cfg,dry_run="--dry-run" in sys.argv))
    except (ValueError,json.JSONDecodeError) as error:
        print(f"Configuration error: {error}",file=sys.stderr)
        sys.exit(2)
