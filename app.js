(() => {
  const tbody = document.getElementById("tbody");
  const searchInput = document.getElementById("search");
  const belowOnly = document.getElementById("below-only");
  const oversub1000 = document.getElementById("oversub-1000");
  const visibleCount = document.getElementById("visible-count");
  const stats = document.getElementById("stats");
  const fetched = document.getElementById("fetched");

  let data = null;
  let sortKey = "cumulative";
  let sortDir = "desc";
  let query = "";

  function parseNumber(value) {
    if (value == null) return NaN;
    const raw = String(value).trim();
    if (!raw || raw === "N/A" || raw === "認購不足" || raw === "-") return NaN;
    // market cap ranges like 667.13-718.27 → use midpoint
    const range = raw.match(
      /^(-?[\d,]+(?:\.\d+)?)\s*-\s*(-?[\d,]+(?:\.\d+)?)$/
    );
    if (range) {
      const a = Number(range[1].replace(/,/g, ""));
      const b = Number(range[2].replace(/,/g, ""));
      return (a + b) / 2;
    }
    const cleaned = raw
      .replace(/,/g, "")
      .replace(/%/g, "")
      .replace(/手/g, "")
      .replace(/^\+/, "");
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : NaN;
  }

  function oneLotCash(item) {
    const hands = parseNumber(item.one_lot);
    const lot = parseNumber(item.lot_size);
    const price =
      parseNumber(item.offer_price) || parseNumber(item.listing_price);
    if ([hands, lot, price].some((n) => Number.isNaN(n))) return NaN;
    return hands * lot * price;
  }

  function formatCash(value) {
    if (Number.isNaN(value)) return "—";
    return (
      "HK$" +
      value.toLocaleString("en-HK", {
        maximumFractionDigits: 0,
      })
    );
  }

  function compare(a, b, key) {
    if (key === "name") {
      return a.name.localeCompare(b.name, "zh-Hant");
    }
    if (key === "listing_date") {
      return String(a.listing_date).localeCompare(String(b.listing_date));
    }
    if (key === "code") {
      return String(a.code).localeCompare(String(b.code));
    }
    const na = key === "one_lot_cash" ? oneLotCash(a) : parseNumber(a[key]);
    const nb = key === "one_lot_cash" ? oneLotCash(b) : parseNumber(b[key]);
    if (Number.isNaN(na) && Number.isNaN(nb)) return 0;
    if (Number.isNaN(na)) return 1;
    if (Number.isNaN(nb)) return -1;
    return na - nb;
  }

  function performanceClass(value) {
    const n = parseNumber(value);
    if (Number.isNaN(n) || n === 0) return "num";
    return n > 0 ? "pos" : "neg";
  }

  function filteredSorted() {
    const q = query.trim().toLowerCase();
    const onlyBelow = Boolean(belowOnly && belowOnly.checked);
    const onlyOver1000 = Boolean(oversub1000 && oversub1000.checked);
    let rows = data.items.filter((item) => {
      if (onlyBelow && item.badge !== "跌穿上市價") return false;
      if (onlyOver1000) {
        const over = parseNumber(item.oversub);
        if (Number.isNaN(over) || over < 1000) return false;
      }
      if (!q) return true;
      return (
        item.name.toLowerCase().includes(q) ||
        String(item.code).toLowerCase().includes(q)
      );
    });
    rows = rows.slice().sort((a, b) => {
      const c = compare(a, b, sortKey);
      return sortDir === "asc" ? c : -c;
    });
    return rows;
  }

  function render() {
    if (!data) return;
    const rows = filteredSorted();
    visibleCount.textContent = `顯示 ${rows.length} / ${data.count}`;
    const frag = document.createDocumentFragment();

    for (const item of rows) {
      const tr = document.createElement("tr");
      const nameHref = item.info_url || item.quote_url || "#";
      const codeHref = item.quote_url || item.info_url || "#";
      const badge = item.badge
        ? `<span class="badge">${escapeHtml(item.badge)}</span>`
        : "";

      tr.innerHTML = `
        <td class="txt-l">
          <div class="name-cell">
            <a href="${escapeAttr(nameHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.name)}</a>
            <span class="code"><a href="${escapeAttr(codeHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.code)}.HK</a></span>
            ${badge}
          </div>
        </td>
        <td class="num">${escapeHtml(item.listing_date)}</td>
        <td class="num">${escapeHtml(item.lot_size)}</td>
        <td class="num">${escapeHtml(item.market_cap)}</td>
        <td class="num">${escapeHtml(item.offer_price)}</td>
        <td class="num">${escapeHtml(item.listing_price)}</td>
        <td class="num">${escapeHtml(item.oversub)}</td>
        <td class="num">${escapeHtml(item.one_lot)}</td>
        <td class="num">${escapeHtml(formatCash(oneLotCash(item)))}</td>
        <td class="num">${escapeHtml(item.allotment)}</td>
        <td class="num">${escapeHtml(item.current_price)}</td>
        <td class="${performanceClass(item.first_day)}">${escapeHtml(item.first_day)}</td>
        <td class="${performanceClass(item.cumulative)}">${escapeHtml(item.cumulative)}</td>
      `;
      frag.appendChild(tr);
    }

    tbody.replaceChildren(frag);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replaceAll("'", "&#39;");
  }

  document.querySelectorAll("th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (sortKey === key) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortKey = key;
        sortDir = key === "name" || key === "listing_date" ? "asc" : "desc";
      }
      document.querySelectorAll("th.sortable").forEach((el) => {
        el.classList.remove("sorted-asc", "sorted-desc");
      });
      th.classList.add(sortDir === "asc" ? "sorted-asc" : "sorted-desc");
      render();
    });
  });

  let searchTimer;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      query = searchInput.value;
      render();
    }, 120);
  });

  function bindFilter(el) {
    if (!el) return;
    const apply = () => render();
    el.addEventListener("change", apply);
    el.addEventListener("input", apply);
    el.addEventListener("click", () => queueMicrotask(apply));
    const label = el.closest("label");
    if (label) {
      label.addEventListener("change", apply);
      label.addEventListener("click", () => queueMicrotask(apply));
    }
  }
  bindFilter(belowOnly);
  bindFilter(oversub1000);

  window
    .loadIpoData({
      api: "/api/listed",
      fallback: "data.json",
      label: "已上市 IPO",
    })
    .then((payload) => {
      if (!payload || !Array.isArray(payload.items)) {
        stats.textContent = "無法載入資料";
        return;
      }
      data = payload;
      stats.textContent = `共 ${data.count} 筆（合併 15 頁）`;
      fetched.textContent = data.fetched_at
        ? `更新於 ${data.fetched_at.replace("T", " ")}`
        : "";
      if (data._refresh_error) {
        fetched.textContent += "（部分更新失敗，已用快取）";
      }
      render();
    })
    .catch((err) => {
      stats.textContent = "無法載入資料";
      fetched.textContent = String(err.message || err);
    });
})();
