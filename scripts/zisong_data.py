"""Single writer for the site's data files.

restaurants.json is the source of truth and keeps every field, including menus.
From it we write:
  data.js   window.RESTAURANTS = [...]   every record WITHOUT the `menu` array
            (homepage / listings load this, so it must stay small)
  menus.js  window.ZISONG_MENUS = {id: menu}   loaded only by detail.html
Static shop/*.html pages render their menus at build time from restaurants.json.

Every script that changes shop data must call write_site_data() (or
write_split_js() after writing restaurants.json itself). Never write data.js by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

MENU_KEY = "menu"


def _line(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def split_records(records: list[dict]) -> tuple[list[dict], dict]:
    lite, menus = [], {}
    for r in records:
        m = r.get(MENU_KEY)
        if m:
            if r["id"] in menus:
                raise ValueError(f"duplicate id with menu: {r['id']}")
            menus[r["id"]] = m
        lite.append({k: v for k, v in r.items() if k != MENU_KEY})
    return lite, menus


def write_split_js(root, records: list[dict]) -> dict:
    """Write data.js (no menus) + menus.js. Returns sizes; raises if a menu would be lost."""
    root = Path(root)
    lite, menus = split_records(records)
    with_menu = sum(1 for r in records if r.get(MENU_KEY))
    if len(menus) != with_menu:
        raise RuntimeError(f"menu count mismatch: {len(menus)} written vs {with_menu} in records")
    data_js = "window.RESTAURANTS = [\n" + ",\n".join(_line(r) for r in lite) + "\n];\n"
    menus_js = (
        "window.ZISONG_MENUS = {\n"
        + ",\n".join(f"{_line(k)}:{_line(v)}" for k, v in menus.items())
        + "\n};\n"
    )
    (root / "data.js").write_text(data_js, encoding="utf-8")
    (root / "menus.js").write_text(menus_js, encoding="utf-8")
    return {"records": len(lite), "menus": len(menus),
            "data_js_bytes": len(data_js.encode()), "menus_js_bytes": len(menus_js.encode())}


def write_site_data(root, records: list[dict]) -> dict:
    """Write restaurants.json (full, incl. menus) + data.js + menus.js."""
    root = Path(root)
    (root / "restaurants.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return write_split_js(root, records)


def load_records(root) -> list[dict]:
    """Always read restaurants.json (data.js has no menus)."""
    return json.loads((Path(root) / "restaurants.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    import sys
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
    print(write_split_js(root, load_records(root)))
