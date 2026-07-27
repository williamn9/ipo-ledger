#!/usr/bin/env python3
"""Scrape AAStocks IPO queue: 正在招股 + 即將上市（含超額倍數）."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
MAIN = "https://www.aastocks.com/tc/stocks/market/ipo/mainpage.aspx"
UPCOMING = "https://www.aastocks.com/tc/stocks/market/ipo/upcomingipo.aspx"


def fetch(url: str, dest: Path, attempts: int = 3) -> None:
    last_err: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            subprocess.run(
                [
                    "curl",
                    "-sL",
                    "--retry",
                    "2",
                    "--retry-delay",
                    "2",
                    "-A",
                    UA,
                    "-H",
                    "Accept-Language: zh-HK,zh;q=0.9,en;q=0.8",
                    "--connect-timeout",
                    "20",
                    "--max-time",
                    "90",
                    url,
                    "-o",
                    str(dest),
                ],
                check=True,
            )
            if dest.stat().st_size > 1000:
                return
            last_err = RuntimeError(f"empty response for {url}")
        except Exception as err:  # noqa: BLE001
            last_err = err
            print(f"  retry {i}/{attempts} failed: {err}")
    raise RuntimeError(f"Failed to fetch {url}") from last_err


def text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", html))).strip()


def abs_url(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return href
    return "https://www.aastocks.com" + href


def table_after_title(html: str, title: str) -> str | None:
    """Return inner HTML of the first <table> after a panel title."""
    # Titles can include nested tags / newlines
    pattern = rf'<div class="title">\s*(?:<a[^>]*>)?\s*{re.escape(title)}'
    m = re.search(pattern, html, re.S)
    if not m:
        return None
    chunk = html[m.start() : m.start() + 12000]
    tm = re.search(r"<table[^>]*>(.*?)</table>", chunk, re.S)
    return tm.group(1) if tm else None


def is_empty_table(table: str) -> bool:
    return bool(re.search(r"errMsg|沒有", table)) and table.count("<tr>") <= 2


def parse_name_cell(td: str) -> tuple[str, str, str, str | None]:
    links = re.findall(r'href="([^"]+)"[^>]*>([^<]+)', td)
    name = links[0][1] if links else text(td)
    href = abs_url(links[0][0]) if links else None
    code_m = re.search(r"(\d{5})\.HK", td)
    code = code_m.group(1) if code_m else ""
    badge_m = re.search(r"label[A-Za-z0-9_-]*[^>]*>([^<]+)", td)
    badge = text(badge_m.group(1)) if badge_m else ""
    return name, code, badge, href


def parse_offering(html: str) -> list[dict]:
    table = table_after_title(html, "正在招股")
    if not table or is_empty_table(table):
        return []
    tbody = re.search(r"<tbody>(.*?)</tbody>", table, re.S)
    body = tbody.group(1) if tbody else table
    out: list[dict] = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 7:
            continue
        name, code, badge, href = parse_name_cell(tds[0])
        out.append(
            {
                "status": "正在招股",
                "name": name,
                "code": code,
                "badge": badge,
                "industry": text(tds[1]),
                "offer_price": text(tds[2]),
                "lot_size": text(tds[3]),
                "entry_fee": text(tds[4]),
                "deadline": text(tds[5]),
                "listing_date": text(tds[6]),
                "grey_date": "",
                "oversub": "尚未公布",
                "allotment": "—",
                "one_lot": "—",
                "info_url": href,
            }
        )
    return out


def parse_grey_upcoming(html: str) -> list[dict]:
    """即將上市新股暗盤 — has oversub / allotment when published."""
    table = table_after_title(html, "即將上市新股暗盤")
    if not table or is_empty_table(table):
        return []
    tbody = re.search(r"<tbody>(.*?)</tbody>", table, re.S)
    body = tbody.group(1) if tbody else table
    out: list[dict] = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        if "errMsg" in tr:
            continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 8:
            continue
        name, code, badge, href = parse_name_cell(tds[0])
        out.append(
            {
                "status": "已截止・待上市",
                "name": name,
                "code": code,
                "badge": badge or "已截止申請",
                "industry": text(tds[1]),
                "offer_price": text(tds[2]),
                "lot_size": "—",
                "entry_fee": "—",
                "deadline": "—",
                "listing_date": text(tds[7]),
                "grey_date": text(tds[6]),
                "oversub": text(tds[3]),
                "allotment": text(tds[4]),
                "one_lot": text(tds[5]),
                "info_url": href,
            }
        )
    return out


def parse_upcoming_list(html: str) -> list[dict]:
    m = re.search(
        r'id="tblGMUpcoming"[^>]*>.*?<tbody>(.*?)</tbody>', html, re.S
    )
    if not m:
        return []
    out: list[dict] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 9:
            continue
        name, code, badge, href = parse_name_cell(tds[1])
        out.append(
            {
                "status": "即將上市",
                "name": name,
                "code": code,
                "badge": badge,
                "industry": text(tds[2]),
                "offer_price": text(tds[3]),
                "lot_size": text(tds[4]),
                "entry_fee": text(tds[5]),
                "deadline": text(tds[6]),
                "listing_date": text(tds[8]),
                "grey_date": text(tds[7]),
                "oversub": "尚未公布",
                "allotment": "—",
                "one_lot": "—",
                "info_url": href,
            }
        )
    return out


def merge_items(*groups: list[dict]) -> list[dict]:
    """Prefer richer oversub data when same code appears twice."""
    by_code: dict[str, dict] = {}
    order: list[str] = []
    for group in groups:
        for item in group:
            code = item["code"] or item["name"]
            if code not in by_code:
                by_code[code] = item
                order.append(code)
                continue
            cur = by_code[code]
            # upgrade oversub if we now have a real number
            if cur.get("oversub") in (None, "", "尚未公布", "—", "N/A") and item.get(
                "oversub"
            ) not in (None, "", "尚未公布", "—", "N/A"):
                cur["oversub"] = item["oversub"]
                cur["allotment"] = item.get("allotment", cur.get("allotment"))
                cur["one_lot"] = item.get("one_lot", cur.get("one_lot"))
                cur["status"] = item["status"]
            # fill blanks
            for k in (
                "industry",
                "offer_price",
                "lot_size",
                "entry_fee",
                "deadline",
                "listing_date",
                "grey_date",
                "badge",
                "info_url",
            ):
                if (not cur.get(k) or cur.get(k) in ("—", "N/A", "")) and item.get(k):
                    cur[k] = item[k]
    return [by_code[c] for c in order]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        main_html = tmp_path / "main.html"
        up_html = tmp_path / "upcoming.html"
        print("Fetching IPO main page...")
        fetch(MAIN, main_html)
        print("Fetching upcoming IPO page...")
        fetch(UPCOMING, up_html)
        main_text = main_html.read_text(encoding="utf-8", errors="replace")
        up_text = up_html.read_text(encoding="utf-8", errors="replace")

    offering = parse_offering(main_text)
    grey = parse_grey_upcoming(main_text)
    upcoming = parse_upcoming_list(up_text)
    items = merge_items(offering, grey, upcoming)

    payload = {
        "source": MAIN,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(items),
        "offering_count": sum(1 for i in items if i["status"] == "正在招股"),
        "pending_count": sum(1 for i in items if i["status"] != "正在招股"),
        "items": items,
        "note": (
            "超額倍數通常喺公開發售截止後／配發結果公布先有數字；"
            "招股進行中多數顯示「尚未公布」。"
        ),
    }

    (ROOT / "queue-data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "queue-data.js").write_text(
        "window.IPO_QUEUE = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(items)} queue IPO(s) to queue-data.json / queue-data.js")
    for it in items:
        print(
            f"  [{it['status']}] {it['name']} {it['code']} "
            f"oversub={it['oversub']} deadline={it['deadline']}"
        )


if __name__ == "__main__":
    main()
