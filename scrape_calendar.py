#!/usr/bin/env python3
"""Build calendar data: IPOs with offer deadline in the next 30 days + oversub news."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
MAIN = "https://www.aastocks.com/tc/stocks/market/ipo/mainpage.aspx"
UPCOMING = "https://www.aastocks.com/tc/stocks/market/ipo/upcomingipo.aspx"
HKET = "https://inews.hket.com/sran009-2/%E6%96%B0%E8%82%A1IPO"
TRADESMART = "https://www.lowrisktradesmart.org/zh-hk/tools/ipo-tracker"


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
                    "-A",
                    UA,
                    "-H",
                    "Accept-Language: zh-HK,zh;q=0.9",
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
            if dest.stat().st_size > 500:
                return
            last_err = RuntimeError("empty response")
        except Exception as err:  # noqa: BLE001
            last_err = err
            print(f"  retry {i}/{attempts}: {err}")
    raise RuntimeError(f"Failed to fetch {url}") from last_err


def text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", html))).strip()


def abs_url(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return href
    return "https://www.aastocks.com" + href


def parse_date(s: str) -> date | None:
    s = (s or "").strip().replace("-", "/")
    for fmt in ("%Y/%m/%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def parse_offering(html: str) -> list[dict]:
    i = html.find("正在招股")
    if i < 0:
        return []
    chunk = html[i : i + 10000]
    tbody = re.search(r"<tbody>(.*?)</tbody>", chunk, re.S)
    if not tbody or "errMsg" in tbody.group(1):
        return []
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", tbody.group(1), re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 7:
            continue
        links = re.findall(r'href="([^"]+)"[^>]*>([^<]+)', tds[0])
        code_m = re.search(r"(\d{5})\.HK", tds[0])
        badge_m = re.search(r"label[A-Za-z0-9_-]*[^>]*>([^<]+)", tds[0])
        out.append(
            {
                "name": links[0][1] if links else text(tds[0]),
                "code": code_m.group(1) if code_m else "",
                "badge": text(badge_m.group(1)) if badge_m else "",
                "industry": text(tds[1]),
                "offer_price": text(tds[2]),
                "lot_size": text(tds[3]),
                "entry_fee": text(tds[4]),
                "deadline": text(tds[5]),
                "listing_date": text(tds[6]),
                "info_url": abs_url(links[0][0]) if links else None,
                "status": "正在招股",
            }
        )
    return out


def parse_upcoming(html: str) -> list[dict]:
    m = re.search(r'id="tblGMUpcoming".*?<tbody>(.*?)</tbody>', html, re.S)
    if not m:
        return []
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 9:
            continue
        links = re.findall(r'href="([^"]+)"[^>]*>([^<]+)', tds[1])
        code_m = re.search(r"(\d{5})\.HK", tds[1])
        out.append(
            {
                "name": links[0][1] if links else text(tds[1]),
                "code": code_m.group(1) if code_m else "",
                "badge": "",
                "industry": text(tds[2]),
                "offer_price": text(tds[3]),
                "lot_size": text(tds[4]),
                "entry_fee": text(tds[5]),
                "deadline": text(tds[6]),
                "listing_date": text(tds[8]),
                "info_url": abs_url(links[0][0]) if links else None,
                "status": "即將上市",
            }
        )
    return out


def parse_grey(html: str) -> list[dict]:
    i = html.find("即將上市新股暗盤")
    if i < 0:
        return []
    chunk = html[i : i + 12000]
    if "沒有" in chunk[:2000]:
        return []
    tbody = re.search(r"<tbody>(.*?)</tbody>", chunk, re.S)
    if not tbody:
        return []
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", tbody.group(1), re.S):
        if "errMsg" in tr:
            continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 8:
            continue
        links = re.findall(r'href="([^"]+)"[^>]*>([^<]+)', tds[0])
        code_m = re.search(r"(\d{5})\.HK", tds[0])
        out.append(
            {
                "name": links[0][1] if links else text(tds[0]),
                "code": code_m.group(1) if code_m else "",
                "industry": text(tds[1]),
                "offer_price": text(tds[2]),
                "oversub": text(tds[3]),
                "allotment": text(tds[4]),
                "one_lot": text(tds[5]),
                "listing_date": text(tds[7]),
                "info_url": abs_url(links[0][0]) if links else None,
                "status": "已截止・待上市",
                "oversub_source": "AAStocks 暗盤表",
            }
        )
    return out


def parse_hket_oversub(html: str) -> dict[str, dict]:
    """Map stock code -> {multiple, note, title} from HKET IPO listing titles."""
    found: dict[str, dict] = {}
    # titles containing 超購/超額 and a 4-5 digit code
    titles = re.findall(r'title="([^"]{10,200})"', html)
    titles += re.findall(r'class="ellipsis"[^>]*>([^<]{10,200})<', html)
    for raw in titles:
        t = unescape(raw)
        if "超購" not in t and "超額" not in t:
            continue
        code_m = re.search(r"(?<!\d)(\d{4,5})(?!\d)", t)
        mult_m = re.search(
            r"(?:超購|超額認購|超額)\s*(?:至少|約|逾|近)?\s*([0-9]+(?:\.[0-9]+)?)\s*倍",
            t,
        )
        if not code_m or not mult_m:
            # e.g. 孖展478億超購7.7倍 with code elsewhere in title
            mult_m = re.search(r"超購\s*([0-9]+(?:\.[0-9]+)?)\s*倍", t)
            if not code_m or not mult_m:
                continue
        code = code_m.group(1).zfill(5)
        multiple = float(mult_m.group(1))
        note = "HKET 新聞標題"
        if "孖展" in t:
            note = "HKET（孖展／公開統計）"
        found[code] = {
            "multiple": multiple,
            "display": f"{multiple:g} 倍",
            "note": note,
            "headline": t[:120],
        }
    return found


def parse_tradesmart_margin(html: str) -> dict[str, dict]:
    h2 = html.replace('\\"', '"').replace("\\/", "/")
    i = h2.find('"records":[')
    if i < 0:
        return {}
    start = h2.find("[", i)
    depth = 0
    arr = None
    for j in range(start, min(start + 80000, len(h2))):
        if h2[j] == "[":
            depth += 1
        elif h2[j] == "]":
            depth -= 1
            if depth == 0:
                try:
                    arr = json.loads(h2[start : j + 1])
                except json.JSONDecodeError:
                    arr = None
                break
    out: dict[str, dict] = {}
    if not arr:
        return out
    for rec in arr:
        code = str(rec.get("symbol", "")).zfill(5)
        ratio = rec.get("oversubscription_ratio")
        if not code or ratio is None:
            continue
        out[code] = {
            "multiple": float(ratio),
            "display": f"{float(ratio):.1f} 倍",
            "note": "市場估算（華盛孖展×校準）",
            "headline": f"{rec.get('name','')} 估計超購 {float(ratio):.1f} 倍",
            "observed_at": rec.get("observed_at"),
        }
    return out


def merge_ipos(*groups: list[dict]) -> dict[str, dict]:
    by: dict[str, dict] = {}
    for group in groups:
        for item in group:
            code = item.get("code") or item.get("name")
            if not code:
                continue
            if code not in by:
                by[code] = dict(item)
            else:
                cur = by[code]
                for k, v in item.items():
                    if v and (not cur.get(k) or cur.get(k) in ("N/A", "—", "")):
                        cur[k] = v
                if item.get("oversub") and cur.get("oversub") in (
                    None,
                    "",
                    "尚未公布",
                    "N/A",
                ):
                    cur["oversub"] = item["oversub"]
                    cur["oversub_source"] = item.get("oversub_source")
    return by


def main() -> None:
    today = date.today()
    until = today + timedelta(days=30)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        main_f = tmp_path / "main.html"
        up_f = tmp_path / "up.html"
        hket_f = tmp_path / "hket.html"
        ts_f = tmp_path / "ts.html"

        print("Fetching AAStocks…")
        fetch(MAIN, main_f)
        fetch(UPCOMING, up_f)
        print("Fetching market news oversub…")
        try:
            fetch(HKET, hket_f)
        except Exception as err:  # noqa: BLE001
            print("  HKET skip:", err)
            hket_f.write_text("", encoding="utf-8")
        try:
            fetch(TRADESMART, ts_f)
        except Exception as err:  # noqa: BLE001
            print("  TradeSmart skip:", err)
            ts_f.write_text("", encoding="utf-8")

        main_html = main_f.read_text(encoding="utf-8", errors="replace")
        up_html = up_f.read_text(encoding="utf-8", errors="replace")
        hket_html = hket_f.read_text(encoding="utf-8", errors="replace")
        ts_html = ts_f.read_text(encoding="utf-8", errors="replace")

    by_code = merge_ipos(
        parse_offering(main_html),
        parse_upcoming(up_html),
        parse_grey(main_html),
    )
    hket_map = parse_hket_oversub(hket_html)
    ts_map = parse_tradesmart_margin(ts_html)

    items = []
    for code, item in by_code.items():
        dd = parse_date(item.get("deadline", ""))
        if not dd or not (today <= dd <= until):
            continue
        ld = parse_date(item.get("listing_date", ""))

        news = []
        primary = None
        # Prefer official AAStocks oversub if numeric
        raw = item.get("oversub")
        if raw and raw not in ("尚未公布", "N/A", "—", ""):
            primary = {
                "multiple": raw,
                "display": f"{raw} 倍" if "倍" not in str(raw) else str(raw),
                "note": item.get("oversub_source") or "AAStocks",
            }
        # Live market margin estimate (often updates during offer)
        if code in ts_map:
            news.append(ts_map[code])
            if primary is None:
                primary = ts_map[code]
        # Press headlines
        if code in hket_map:
            news.append(hket_map[code])
            if primary is None:
                primary = hket_map[code]

        items.append(
            {
                **item,
                "deadline_iso": dd.isoformat(),
                "listing_date_iso": ld.isoformat() if ld else "",
                "oversub_primary": primary["display"] if primary else "尚未見報道",
                "oversub_multiple": primary.get("multiple") if primary else None,
                "oversub_note": primary.get("note") if primary else "招股中／未見超購消息",
                "news": news,
            }
        )

    items.sort(key=lambda x: x["deadline_iso"])

    payload = {
        "as_of": today.isoformat(),
        "window_end": until.isoformat(),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(items),
        "items": items,
        "sources": [
            "AAStocks 正在招股／即將上市",
            "HKET 新股新聞（超購報道）",
            "市場孖展估算（如有）",
        ],
        "note": (
            "未來 30 日以 AAStocks 招股截止日期為準；超額倍數來自市場新聞／孖展統計，"
            "招股進行中數字可能隨時更新，最終以配發結果為準。"
        ),
    }

    (ROOT / "calendar-data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "calendar-data.js").write_text(
        "window.IPO_CALENDAR = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(items)} IPO(s) deadline {today} → {until}")
    for it in items:
        print(
            f"  {it['deadline_iso']} {it['name']} {it['code']} "
            f"list={it.get('listing_date_iso') or '—'} "
            f"oversub={it['oversub_primary']}"
        )


if __name__ == "__main__":
    main()
