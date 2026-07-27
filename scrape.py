#!/usr/bin/env python3
"""Fetch the latest listed IPO page from AAStocks and write data.json / data.js."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = "https://www.aastocks.com/tc/stocks/market/ipo/listedipo.aspx?s=3&o=0&page=1"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_page(dest: Path) -> None:
    subprocess.run(
        [
            "curl",
            "-sL",
            "-A",
            UA,
            "-H",
            "Accept-Language: zh-HK,zh;q=0.9,en;q=0.8",
            "--max-time",
            "45",
            URL,
            "-o",
            str(dest),
        ],
        check=True,
    )


def abs_url(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return href
    return "https://www.aastocks.com" + href


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", html))).strip()


def extract_table_body(html: str) -> str:
    start = html.find('<div id="IPOListed"')
    if start < 0:
        raise RuntimeError("IPOListed table not found — page markup may have changed")
    chunk = html[start:]
    tstart = chunk.find("<tbody>")
    tend = chunk.find("</tbody>", tstart)
    if tstart < 0 or tend < 0:
        raise RuntimeError("tbody not found")
    return chunk[tstart : tend + 8]


def parse_page(html: str) -> list[dict]:
    body = extract_table_body(html)
    rows: list[dict] = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 13:
            continue

        name_td = tds[1]
        links = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', name_td, re.S)
        name = ""
        code = ""
        info_url = quote_url = None
        for href, text in links:
            text = text_of(text)
            if "company-summary" in href or "upcomingipo" in href:
                name = text
                info_url = abs_url(href)
            elif "detail-quote" in href:
                code = re.sub(r"\.HK$", "", text).strip()
                quote_url = abs_url(href)

        badge_m = re.search(r'class="lowInd"[^>]*>(.*?)</div>', name_td, re.S)
        badge = text_of(badge_m.group(1)) if badge_m else ""
        if code.isdigit():
            code = code.zfill(5)

        rows.append(
            {
                "name": name,
                "code": code,
                "badge": badge,
                "listing_date": text_of(tds[2]),
                "lot_size": text_of(tds[3]),
                "market_cap": text_of(tds[4]),
                "offer_price": text_of(tds[5]),
                "listing_price": text_of(tds[6]),
                "oversub": text_of(tds[7]),
                "one_lot": text_of(tds[8]),
                "allotment": text_of(tds[9]),
                "current_price": text_of(tds[10]),
                "first_day": text_of(tds[11]),
                "cumulative": text_of(tds[12]),
                "quote_url": quote_url,
                "info_url": info_url,
            }
        )
    return rows


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "page_1.html"
        print("Fetching latest listed IPO page…")
        fetch_page(dest)
        html = dest.read_text(encoding="utf-8", errors="replace")
        rows = parse_page(html)
        print(f"  {len(rows)} rows")

    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for row in rows:
        key = (row["code"], row["listing_date"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    payload = {
        "source": URL,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(unique),
        "page": 1,
        "items": unique,
    }

    (ROOT / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (ROOT / "data.js").write_text(
        "window.IPO_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(unique)} IPOs to data.json and data.js")


if __name__ == "__main__":
    main()
