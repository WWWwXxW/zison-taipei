#!/usr/bin/env python3
"""Merge full Scout corpus into restaurants.json. Merchant channels only; dedupe name+district & order URL."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path("/workspace/taipei-own-delivery-leads.md")
TODAY = date.today().isoformat()

DISTRICT_CANON = {
    "中正": "中正區", "中正區": "中正區",
    "大同": "大同區", "大同區": "大同區",
    "中山": "中山區", "中山區": "中山區",
    "松山": "松山區", "松山區": "松山區",
    "大安": "大安區", "大安區": "大安區",
    "萬華": "萬華區", "萬華區": "萬華區",
    "信義": "信義區", "信義區": "信義區",
    "士林": "士林區", "士林區": "士林區",
    "北投": "北投區", "北投區": "北投區",
    "內湖": "內湖區", "內湖區": "內湖區",
    "南港": "南港區", "南港區": "南港區",
    "文山": "文山區", "文山區": "文山區",
}
DISTRICT_SHORT = {v: k for k, v in DISTRICT_CANON.items() if not k.endswith("區")}

PLATFORM_HOST_RE = re.compile(
    r"(ubereats\.com|uber\.com|foodpanda\.(tw|com)|deliveryhero|"
    r"google\.(com|com\.tw)/maps|maps\.app\.goo\.gl|ifoodie\.tw|"
    r"openrice\.com)",
    re.I,
)
BOOKING_RE = re.compile(r"inline\.app/booking|openrice\.com/.*/booking", re.I)
DIRECTORY_HOST_RE = re.compile(
    r"(ifoodie\.tw|openrice\.com|google\.(com|com\.tw)|maps\.app\.goo\.gl|"
    r"facebook\.com|instagram\.com|yelp\.|tripadvisor\.)",
    re.I,
)
URL_RE = re.compile(r"https?://[^\s|;,）)\]]+", re.I)
PHONE_RE = re.compile(
    r"(?:\+?886[-\s]?)?(?:0?9\d{2}[-\s]?\d{3}[-\s]?\d{3}|0?2[-\s]?\d{3,4}[-\s]?\d{4})",
)
LINE_AT_RE = re.compile(r"(?:LINE\s*)?@([a-zA-Z0-9._-]{3,})", re.I)
ADDR_RE = re.compile(
    r"([\u4e00-\u9fff]{0,6}(?:路|街|道|大道|巷|弄|段)[^\s;；|]{0,30}\d+[-\d]*號?(?:之\d+)?(?:\d+樓)?)"
)

KNOWN_UNQUALIFIED_PREFIXES = ("ABV ", "ABV Bar")
KNOWN_UNQUALIFIED = {
    "ABV Bar & Kitchen（ABV Delivery 美味直送）",
    "ABV Bar & Kitchen Delivery",
    "ABV Bar & Kitchen",
}

LEAD_RE = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*\|\s*(.+)$", re.M)
BATCH_HDR_RE = re.compile(r"^## Batch (\d+)\b", re.M)
SUFFIX_RE = re.compile(
    r"(house|restaurant|kitchen|cafe|café|diner|bistro|餐廳|小館|食堂|飯店|酒店)$",
    re.I,
)


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def norm_name(s: str) -> str:
    s = nfkc(s).strip()
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    s = re.sub(r"\s+", "", s)
    s = SUFFIX_RE.sub("", s)
    return s.casefold()


def norm_url(u: str | None) -> str | None:
    if not u:
        return None
    u = u.strip().rstrip(").,;，。；]")
    try:
        p = urlparse(u)
    except Exception:
        return u.rstrip("/").lower()
    host = (p.netloc or "").lower()
    path = (p.path or "").rstrip("/")
    # Oddle storefront: collapse language /stores suffixes for dedupe
    path = re.sub(r"/(en_TW|zh_TW|zh_CN)(/stores)?$", "", path, flags=re.I)
    path = re.sub(r"/stores$", "", path, flags=re.I)
    return urlunparse(
        ("https" if p.scheme.startswith("http") else p.scheme, host, path, "", "", "")
    ).lower()


def clean_url(u: str) -> str:
    return u.strip().rstrip(").,;，。；]")


def is_platform(u: str) -> bool:
    return bool(PLATFORM_HOST_RE.search(u))


def is_booking_only(u: str) -> bool:
    return bool(BOOKING_RE.search(u))


def is_directory(u: str) -> bool:
    return bool(DIRECTORY_HOST_RE.search(u))


def is_line_url(u: str) -> bool:
    host = urlparse(u).netloc.lower()
    return host in {"line.me", "page.line.me", "lin.ee"} or host.endswith(".line.me")


def pick_district(area: str) -> str:
    area_n = nfkc(area)
    found = []
    for key in (
        "大安", "中山", "信義", "松山", "中正", "萬華", "內湖", "南港",
        "士林", "文山", "大同", "北投",
    ):
        if key in area_n:
            found.append(key)
    if len(found) == 1 and not re.search(r"多店|多門市|多區|multi|citywide", area_n, re.I):
        return DISTRICT_CANON[found[0]]
    if len(found) > 1 or re.search(r"多店|多門市|多區|multi|citywide", area_n, re.I):
        return "台北多區"
    if area_n.strip() in {"台北市", "台北", "臺北市", "臺北"}:
        return "台北多區"
    for tok in re.split(r"[・·/／、,，\s（）()]+", area_n):
        tok = tok.strip()
        if tok in DISTRICT_CANON:
            return DISTRICT_CANON[tok]
    return "台北多區"


def cuisine_tags(cuisine: str) -> list[str]:
    cuisine = nfkc(cuisine).strip()
    if not cuisine or cuisine.upper() == "UNKNOWN":
        return []
    parts = re.split(r"[／/、,，|｜]+", cuisine)
    tags = [p.strip() for p in parts if p.strip()]
    return tags or [cuisine]


def channel_urls_and_phone(contact: str) -> tuple[list[str], list[str], str | None]:
    """Return (merchant_urls, line_urls, phone)."""
    contact = nfkc(contact)
    urls = [clean_url(u) for u in URL_RE.findall(contact)]
    merchant_urls: list[str] = []
    line_urls: list[str] = []
    for u in urls:
        if is_platform(u) or is_booking_only(u) or is_directory(u):
            continue
        if is_line_url(u):
            line_urls.append(u)
        else:
            merchant_urls.append(u)
    # LINE @id without URL
    for m in LINE_AT_RE.finditer(contact):
        lid = m.group(1)
        # skip if looks like part of email domain noise
        candidate = f"https://line.me/R/ti/p/@{lid}"
        if not any(lid.lower() in x.lower() for x in line_urls):
            line_urls.append(candidate)

    phones = PHONE_RE.findall(contact)
    phone = re.sub(r"\s+", "", phones[0]) if phones else None
    return merchant_urls, line_urls, phone


def pick_primary(merchant_urls: list[str], line_urls: list[str]) -> tuple[str | None, str | None]:
    """Prefer known order platforms over generic brand pages."""
    def score(u: str) -> int:
        host = urlparse(u).netloc.lower()
        path = urlparse(u).path.lower()
        if "oddle.me" in host:
            return 100
        if "ichefpos.com" in host:
            return 95
        if "dudooeat.com" in host:
            return 90
        if "inline.app" in host and "/order" in path:
            return 88
        if "nidin.shop" in host or "ocard.co" in host:
            return 85
        if is_line_url(u):
            return 80
        if re.search(r"order|訂[購餐]|delivery|外送|takeout|外帶", u, re.I):
            return 70
        return 40

    ordered = sorted(merchant_urls, key=score, reverse=True)
    order = ordered[0] if ordered else (line_urls[0] if line_urls else None)
    line = line_urls[0] if line_urls else (order if order and is_line_url(order) else None)
    return order, line


def extract_address(notes: str) -> str | None:
    notes = nfkc(notes or "")
    notes = re.sub(r"\*\*Maps[^*]*\*\*", "", notes)
    m = ADDR_RE.search(notes)
    if not m:
        return None
    addr = m.group(1).strip().rstrip("；;，,")
    return addr if len(addr) >= 4 else None


def assign_batches(md: str) -> dict[int, int]:
    headers = [(m.start(), int(m.group(1))) for m in BATCH_HDR_RE.finditer(md)]
    out: dict[int, int] = {}
    for m in LEAD_RE.finditer(md):
        num = int(m.group(1))
        pos = m.start()
        batch = 1
        for hpos, b in headers:
            if hpos < pos:
                batch = b
            else:
                break
        out[num] = batch
    return out


def parse_leads(md: str) -> list[dict]:
    batch_of = assign_batches(md)
    leads = []
    for m in LEAD_RE.finditer(md):
        num = int(m.group(1))
        name = m.group(2).strip()
        parts = [p.strip() for p in m.group(3).split("|")]
        if len(parts) == 9:
            _city, area, cuisine, evidence, contact, hours, notes, source, confidence = parts
        elif len(parts) == 8:
            area, cuisine, evidence, contact, hours, notes, source, confidence = parts
        else:
            continue
        confidence = re.sub(r"\*+", "", confidence).strip()
        conf_l = confidence.lower()
        if conf_l.startswith("high"):
            confidence = "high"
        elif conf_l.startswith("medium"):
            confidence = "medium"
        elif conf_l.startswith("low"):
            confidence = "low"

        district = pick_district(area)
        merchant_urls, line_urls, phone = channel_urls_and_phone(contact)
        if not phone:
            ph2 = PHONE_RE.findall(nfkc(notes))
            if ph2:
                phone = re.sub(r"\s+", "", ph2[0])
        order_url, line_url = pick_primary(merchant_urls, line_urls)
        all_urls = list(dict.fromkeys(merchant_urls + line_urls))

        hours_clean = None if not hours or hours.upper() == "UNKNOWN" else hours.strip()
        leads.append(
            {
                "num": num,
                "batch": batch_of.get(num, 1),
                "name": name,
                "district": district,
                "area_raw": area,
                "cuisine": cuisine.strip(),
                "cuisineTags": cuisine_tags(cuisine),
                "evidence": evidence.strip(),
                "orderUrl": order_url,
                "lineUrl": line_url,
                "allUrls": all_urls,
                "phone": phone,
                "hours": hours_clean,
                "address": extract_address(notes),
                "source": source.strip(),
                "confidence": confidence,
            }
        )
    return leads


def make_id(num: int, batch: int, existing_ids: set[str]) -> str:
    # Prefer scout-lead-{num} to avoid colliding with Oddle discover scout-b5-* ids
    for cand in (f"scout-lead-{num}", f"scout-corpus-{num}", f"scout-b{batch}-{num}-c"):
        if cand not in existing_ids:
            return cand
    return f"scout-corpus-{num}-{TODAY.replace('-', '')}"


def lead_to_record(lead: dict, rid: str) -> dict:
    slug = re.sub(r"\s+", "", lead["name"])
    slug = re.sub(r"[（(].*?[）)]", "", slug)[:40] or lead["name"][:40]
    rec: dict = {
        "id": rid,
        "slug": slug,
        "name": lead["name"],
        "district": lead["district"],
        "cuisine": lead["cuisine"],
        "cuisineTags": lead["cuisineTags"],
        "chain": False,
        "featured": False,
        "origin": "scout",
        "confidence": lead["confidence"],
        "checkedAt": TODAY,
    }
    if lead.get("hours"):
        rec["hours"] = lead["hours"]
    if lead.get("evidence"):
        rec["evidence"] = lead["evidence"]
    if lead.get("source"):
        rec["source"] = lead["source"]
    if lead.get("orderUrl"):
        rec["orderUrl"] = lead["orderUrl"]
    if lead.get("lineUrl"):
        rec["lineUrl"] = lead["lineUrl"]
        if not rec.get("orderUrl"):
            rec["orderUrl"] = lead["lineUrl"]
    if lead.get("phone"):
        rec["phone"] = lead["phone"]
    if lead.get("address"):
        rec["address"] = lead["address"]
    return rec


def has_merchant_channel(lead: dict) -> bool:
    return bool(lead.get("orderUrl") or lead.get("lineUrl") or lead.get("phone") or lead.get("allUrls"))


def main() -> None:
    md = CORPUS.read_text(encoding="utf-8")
    existing = json.loads((ROOT / "restaurants.json").read_text(encoding="utf-8"))
    before = len(existing)

    existing_ids = {r["id"] for r in existing}
    name_district: set[tuple[str, str]] = set()
    names_any: dict[str, set[str]] = {}
    order_urls: set[str] = set()
    brand_hosts: set[str] = set()
    _MULTI = (
        "oddle.me", "ichefpos.com", "dudooeat.com", "inline.app",
        "nidin.shop", "ocard.co", "line.me", "lin.ee", "quickclick.cc",
        "myship.7-11.com.tw",
    )

    def _brand_host(u: str | None) -> str | None:
        if not u:
            return None
        try:
            h = urlparse(u).netloc.lower()
        except Exception:
            return None
        if h.startswith("www."):
            h = h[4:]
        if any(h == s or h.endswith("." + s) for s in _MULTI):
            return None
        return h

    for r in existing:
        nn = norm_name(r.get("name") or "")
        dist = r.get("district") or ""
        name_district.add((nn, dist))
        names_any.setdefault(nn, set()).add(dist)
        for key in ("orderUrl", "lineUrl"):
            nu = norm_url(r.get(key))
            if nu:
                order_urls.add(nu)
            bh = _brand_host(r.get(key))
            if bh:
                brand_hosts.add(bh)

    leads = parse_leads(md)
    skip_reasons: Counter[str] = Counter()
    skipped_sample: list[dict] = []
    added: list[dict] = []

    def note_skip(lead: dict, reason: str) -> None:
        skip_reasons[reason] += 1
        if len(skipped_sample) < 50:
            skipped_sample.append({"num": lead["num"], "name": lead["name"], "reason": reason})

    for lead in leads:
        if lead["name"] in KNOWN_UNQUALIFIED or lead["name"].startswith(KNOWN_UNQUALIFIED_PREFIXES):
            note_skip(lead, "known_unqualified")
            continue
        if not has_merchant_channel(lead):
            note_skip(lead, "no_channel")
            continue

        nn = norm_name(lead["name"])
        dist = lead["district"]

        # name + district
        if (nn, dist) in name_district:
            note_skip(lead, "dup_name_district")
            continue

        # same name already listed under 台北多區 or new is multi covering existing district
        if nn in names_any:
            existing_dists = names_any[nn]
            if dist == "台北多區" or "台北多區" in existing_dists:
                note_skip(lead, "dup_name_district")
                continue
            # area raw mentions an existing district short name for same brand name
            area = lead.get("area_raw") or ""
            overlap = False
            for ed in existing_dists:
                short = DISTRICT_SHORT.get(ed, ed.replace("區", ""))
                if short and short in area:
                    overlap = True
                    break
            if overlap:
                note_skip(lead, "dup_name_district")
                continue

        # any channel URL already known
        lead_norms = [norm_url(u) for u in lead.get("allUrls") or []]
        lead_norms = [u for u in lead_norms if u]
        if any(u in order_urls for u in lead_norms):
            note_skip(lead, "dup_order_url")
            continue

        # brand-site host match (non multi-tenant): vegetsai.com.tw/ vs /orderinfo.html
        MULTI_TENANT_SUFFIXES = (
            "oddle.me", "ichefpos.com", "dudooeat.com", "inline.app",
            "nidin.shop", "ocard.co", "line.me", "lin.ee", "quickclick.cc",
            "myship.7-11.com.tw",
        )
        def brand_host(u: str) -> str | None:
            try:
                h = urlparse(u).netloc.lower()
            except Exception:
                return None
            if h.startswith("www."):
                h = h[4:]
            if any(h == s or h.endswith("." + s) for s in MULTI_TENANT_SUFFIXES):
                return None
            return h
        lead_hosts = {brand_host(u) for u in (lead.get("allUrls") or [])}
        lead_hosts.discard(None)
        if lead_hosts & brand_hosts:
            note_skip(lead, "dup_order_url")
            continue

        rid = make_id(lead["num"], lead["batch"], existing_ids)
        rec = lead_to_record(lead, rid)
        added.append(rec)
        existing_ids.add(rid)
        name_district.add((nn, dist))
        names_any.setdefault(nn, set()).add(dist)
        for u in lead_norms:
            order_urls.add(u)
        for u in lead.get("allUrls") or []:
            bh = _brand_host(u)
            if bh:
                brand_hosts.add(bh)

    merged = existing + added
    (ROOT / "restaurants.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "data.js").write_text(
        "window.RESTAURANTS = " + json.dumps(merged, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    report = {
        "before": before,
        "after": len(merged),
        "added": len(added),
        "leads_parsed": len(leads),
        "corpus_digest_total": 517,
        "skipped": sum(skip_reasons.values()),
        "skip_reasons": dict(skip_reasons),
        "added_ids": [r["id"] for r in added],
        "added_names": [r["name"] for r in added],
        "skipped_sample": skipped_sample,
        "policy": (
            "KEEP merchant channels only (own web / Oddle / LINE / phone / iCHEF / dudoo / "
            "inline.app/order / brand order). Exclude UE/Foodpanda-only, booking-only, "
            "directory-only. Dedupe name+district (incl. multi↔district) and all channel URLs. "
            "IDs use scout-lead-{n} to avoid Oddle scout-b5-* collisions. ABV known_unqualified."
        ),
        "checkedAt": TODAY,
    }
    (ROOT / "scout-leads-merge-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: report[k] for k in ("before", "after", "added", "leads_parsed", "skipped", "skip_reasons")},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
