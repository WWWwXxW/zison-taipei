# -*- coding: utf-8 -*-
"""Reader-facing cleanup for shop notes.

Internal English labels (Range, Minimum / shipping, Free-delivery threshold, …)
are translated into Traditional Chinese. A segment whose value is UNKNOWN,
unknown, empty, N/A, or TODO is dropped. Nothing is invented: numbers, ranges,
and fees are only reformatted from values already present.
免運門檻 stays inside the summary string (secondary text). It is never written
into deliveryMinLabel or any primary badge field.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
import sys as _zs_sys
from pathlib import Path as _ZsPath
for _zs_p in (_ZsPath(__file__).resolve().parent, _ZsPath(__file__).resolve().parent / "scripts"):
    if str(_zs_p) not in _zs_sys.path:
        _zs_sys.path.insert(0, str(_zs_p))
from zisong_data import write_split_js  # data.js without menus + menus.js


# Longer labels first so "Delivery fee (min listed)" wins over "Delivery fee".
_LABELS = [
    ("Delivery fee (min listed)", "最低運費", False),
    ("Delivery fee max listed", "最高運費", False),
    ("Free-delivery threshold", "免運門檻", True),
    ("Minimum / shipping", "起送", False),
    ("Minimum order", "起送", False),
    ("Delivery fee", "運費", False),
    ("LINE ID", "LINE ID", False),
    ("LINE", "LINE", False),
    ("Range", "外送範圍", False),
]
_LABEL_RE = re.compile(
    r"(?:^|[；;])\s*("
    + "|".join(re.escape(name) for name, _zh, _sec in sorted(_LABELS, key=lambda x: -len(x[0])))
    + r")\s*:\s*"
)
_LABEL_ZH = {name: (zh, secondary) for name, zh, secondary in _LABELS}

_BLANK_RE = re.compile(
    r"(?i)^(?:unknown|n/a|na|todo|null|none|undefined|-+|—+|未提供)?$"
)
_UNKNOWN_WORD = re.compile(r"(?i)\bUNKNOWN\b")
_HOURS_PREFIX = re.compile(r"(?i)^hours\s+")


def is_blankish(value: str | None) -> bool:
    if value is None:
        return True
    s = str(value).strip().strip("；;。．")
    return not s or bool(_BLANK_RE.fullmatch(s))


def _format_amount(raw: str) -> str | None:
    s = raw.strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", s):
        return None
    if "." in s:
        n = float(s)
        if n.is_integer():
            return f"NT${int(n):,}"
        return f"NT${n}"
    return f"NT${int(s):,}"


def _format_threshold(raw: str) -> str | None:
    """Present a free-delivery value that is already in the source. Drop blanks."""
    if is_blankish(raw):
        return None
    amount = _format_amount(raw)
    if amount:
        return amount
    text = raw.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            parts = []
            for key, val in obj.items():
                label = _distance_key(str(key))
                if not label or isinstance(val, bool) or not isinstance(val, (int, float)):
                    continue
                shown = int(val) if float(val).is_integer() else val
                parts.append(f"{label} NT${shown:,}" if isinstance(shown, int) else f"{label} NT${shown}")
            return "、".join(parts) if parts else None
    if _UNKNOWN_WORD.search(text):
        text = _UNKNOWN_WORD.sub("未公開", text).strip("；; ")
        if is_blankish(text) or text == "未公開":
            return None
    return text or None


def _distance_key(key: str) -> str | None:
    known = {
        "within500m": "500公尺內",
        "within1km": "1公里內",
        "within2km": "2公里內",
    }
    if key in known:
        return known[key]
    m = re.fullmatch(r"within(\d+)(m|km)", key)
    if not m:
        return None
    n, unit = m.group(1), m.group(2)
    return f"{n}公尺內" if unit == "m" else f"{n}公里內"


def _clean_segment_value(label: str, value: str) -> str | None:
    value = value.strip().strip("；")
    value = re.sub(r"\s+", " ", value).strip()
    if is_blankish(value):
        return None
    if label == "Free-delivery threshold":
        return _format_threshold(value)
    if label == "Delivery fee":
        amount = _format_amount(value)
        if amount:
            return amount
        if is_blankish(value):
            return None
    if _UNKNOWN_WORD.search(value):
        value = _UNKNOWN_WORD.sub("未公開", value).strip("；; ")
        if is_blankish(value) or value == "未公開":
            return None
    return value or None


def public_terms(text: str | None) -> str | None:
    """Translate the internal terms template. Returns None when nothing remains."""
    if not isinstance(text, str):
        return text
    raw = text.strip()
    if not raw:
        return None
    if not _LABEL_RE.search(raw):
        return _clean_prose(raw)

    matches = list(_LABEL_RE.finditer(raw))
    primary = []
    secondary = []
    tail = []
    for i, match in enumerate(matches):
        label = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        # The next match may include a leading ； that belongs to the separator.
        value = raw[start:end]
        value = re.sub(r"[；;]\s*$", "", value)
        shown = _clean_segment_value(label, value)
        if shown is None:
            continue
        zh, is_secondary = _LABEL_ZH[label]
        piece = f"{zh}：{shown}"
        if label in ("LINE", "LINE ID"):
            tail.append(piece)
        elif is_secondary:
            secondary.append(piece)
        else:
            primary.append(piece)
    parts = primary + secondary + tail
    if not parts:
        return None
    return "；".join(parts)


def _clean_prose(text: str | None) -> str | None:
    if not isinstance(text, str):
        return text
    t = text.replace("**", "")
    t = _UNKNOWN_WORD.sub("未公開", t)
    t = re.sub(r"(?i)\bbrand URL\b", "品牌網址", t)
    t = re.sub(r"(?i)deliveryCreatable:\s*true、?", "", t)
    t = re.sub(r"(?i)QA pass:\s*food-order\s*\+\s*Delivery", "確認為外送訂餐頁", t)
    t = re.sub(r"\s*→\s*medium\b", "", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"；{2,}", "；", t)
    t = t.strip("；; \t")
    if is_blankish(t) or t == "未公開":
        return None
    return t


def public_hours(text: str | None) -> str | None:
    if not isinstance(text, str):
        return text
    t = text.strip()
    if not t:
        return None
    t = _HOURS_PREFIX.sub("", t).strip()
    if is_blankish(t):
        return None
    t = t.replace("**", "")
    if _UNKNOWN_WORD.search(t):
        t = _UNKNOWN_WORD.sub("未公開", t).strip()
    t = t.strip("；; ")
    if not t or t == "未公開":
        # Entire value was UNKNOWN — drop it rather than show a placeholder hour.
        if _UNKNOWN_WORD.search(text) and "（" not in text and "(" not in text:
            return None
    if t == "未公開":
        return None
    return t or None


def public_phone(text: str | None) -> str | None:
    if not isinstance(text, str):
        return text
    if is_blankish(text) or _UNKNOWN_WORD.fullmatch(text.strip() or ""):
        return None
    if _UNKNOWN_WORD.search(text) and is_blankish(_UNKNOWN_WORD.sub("", text)):
        return None
    return text


def public_address(text: str | None) -> str | None:
    if not isinstance(text, str):
        return text
    t = text.replace("**", "").strip()
    return t or None


def public_source(text: str | None) -> str | None:
    """Drop internal segments whose value is UNKNOWN. Strip markdown asterisks."""
    if not isinstance(text, str):
        return text
    parts = [p.strip() for p in text.split("；")]
    kept = []
    for part in parts:
        if not part:
            continue
        m = re.match(r"^(.*?):\s*(.*)$", part)
        if m and is_blankish(m.group(2)):
            continue
        if _UNKNOWN_WORD.search(part):
            cleaned = _UNKNOWN_WORD.sub("", part).strip(" :：")
            if not cleaned or re.fullmatch(r"(?i)phone", cleaned):
                continue
        part = _clean_prose(part) or ""
        if not part or re.fullmatch(r"(?i)phone", part):
            continue
        kept.append(part)
    out = "；".join(kept).strip()
    return out or None


_READER_FIELDS = {
    "terms": public_terms,
    "evidence": _clean_prose,
    "hours": public_hours,
    "phone": public_phone,
    "address": public_address,
    "source": public_source,
    "range": _clean_prose,
    "deliveryNote": _clean_prose,
    "deliveryNotes": _clean_prose,
}


def sanitize_record(record: dict) -> dict:
    """Return a copy with reader-facing strings cleaned.

    deliveryMin* is left untouched so a free-delivery threshold is never
    promoted into the primary 起送 field.
    """
    out = dict(record)
    for key, fn in _READER_FIELDS.items():
        if key not in out:
            continue
        val = out.get(key)
        if isinstance(val, str):
            out[key] = fn(val)
    return out


def sanitize_records(rows: list) -> list:
    return [sanitize_record(r) if isinstance(r, dict) else r for r in rows]


def html_variants(text: str) -> list[str]:
    """Raw string plus the escaped form used inside HTML text."""
    if not text:
        return []
    escaped = html.escape(text, quote=False)
    if escaped == text:
        return [text]
    return [text, escaped]


def apply_html_replacement(text: str, old: str, new: str) -> str:
    if not old:
        return text
    new = new or ""
    if old in text:
        text = text.replace(old, new)
    old_e = html.escape(old, quote=False)
    new_e = html.escape(new, quote=False) if new else ""
    if old_e != old and old_e in text:
        text = text.replace(old_e, new_e)
    return text


def scrub_html(text: str) -> str:
    """Remove reader rows whose value was dropped entirely."""
    text = re.sub(r'<p class="hours">時段：\s*</p>', "", text)
    text = re.sub(r'<p class="hours">時段：UNKNOWN</p>', "", text)
    text = re.sub(r'<p class="hours">時段：hours UNKNOWN</p>', "", text)
    text = re.sub(
        r"<div><dt>營業時間</dt><dd>(?:hours\s+)?UNKNOWN</dd></div>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"<div><dt>電話</dt><dd>UNKNOWN</dd></div>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<div><dt>營業時間</dt><dd></dd></div>", "", text)
    text = re.sub(r"<div><dt>電話</dt><dd></dd></div>", "", text)
    text = re.sub(r"<div><dt>說明／條件摘要</dt><dd></dd></div>", "", text)
    text = re.sub(r"<div><dt>收錄依據摘要</dt><dd></dd></div>", "", text)
    return text


def rewrite_tree(root: Path) -> dict:
    """Rewrite restaurants.json, data.js, and HTML pages. Returns counts."""
    root = Path(root)
    data_path = root / "restaurants.json"
    rows = json.loads(data_path.read_text(encoding="utf-8"))
    replacements: list[tuple[str, str]] = []
    seen = set()
    terms_changed = 0
    records_changed = 0

    cleaned = []
    for row in rows:
        new = sanitize_record(row)
        changed = False
        for key in _READER_FIELDS:
            old = row.get(key)
            now = new.get(key)
            if old == now:
                continue
            changed = True
            if key == "terms" and isinstance(old, str):
                terms_changed += 1
            if isinstance(old, str) and old.strip():
                pair = (old, now or "")
                if pair not in seen:
                    seen.add(pair)
                    replacements.append(pair)
        if changed:
            records_changed += 1
        cleaned.append(new)

    data_path.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_split_js(root, cleaned)

    replacements.sort(key=lambda pair: -len(pair[0]))
    html_changed = 0
    for path in root.rglob("*.html"):
        if any(part in {".git", "node_modules"} for part in path.parts):
            continue
        original = path.read_text(encoding="utf-8")
        text = original
        if "UNKNOWN" in text or "Free-delivery threshold" in text or "Range: " in text or "**" in text or "Minimum / shipping" in text or "Minimum order:" in text or "hours UNKNOWN" in text:
            for old, new in replacements:
                if old in text or html.escape(old, quote=False) in text:
                    text = apply_html_replacement(text, old, new)
            text = scrub_html(text)
        if text != original:
            path.write_text(text, encoding="utf-8")
            html_changed += 1

    blob = (root / "data.js").read_text(encoding="utf-8")
    return {
        "shops": len(cleaned),
        "records_changed": records_changed,
        "terms_rewritten": terms_changed,
        "html_changed": html_changed,
        "unknown_in_data_js": blob.count("UNKNOWN"),
        "free_delivery_label_in_data_js": blob.count("Free-delivery threshold"),
    }


if __name__ == "__main__":
    stats = rewrite_tree(Path(__file__).resolve().parents[1])
    print(json.dumps(stats, ensure_ascii=False, indent=2))
