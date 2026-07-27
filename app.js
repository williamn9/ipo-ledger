(() => {
  const listEl = document.getElementById("listed-list");
  const searchInput = document.getElementById("search");
  const belowOnly = document.getElementById("below-only");
  const oversub1000 = document.getElementById("oversub-1000");
  const sortKeyEl = document.getElementById("sort-key");
  const visibleCount = document.getElementById("visible-count");
  const stats = document.getElementById("stats");
  const fetched = document.getElementById("fetched");

  let data = null;
  let sortKey = sortKeyEl ? sortKeyEl.value : "cumulative";
  let query = "";

  function parseNumber(value) {
    if (value == null) return NaN;
    const raw = String(value).trim();
    if (!raw || raw === "N/A" || raw === "認購不足" || raw === "-") return NaN;
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
    const asc = sortKey === "listing_date" || sortKey === "name";
    rows = rows.slice().sort((a, b) => {
      const c = compare(a, b, sortKey);
      return asc ? c : -c;
    });
    return rows;
  }

  function metric(label, value, className = "num") {
    return `<div class="listed-metric">
      <span class="listed-metric-label">${escapeHtml(label)}</span>
      <span class="${className}">${value}</span>
    </div>`;
  }

  function render() {
    if (!data) return;
    const rows = filteredSorted();
    visibleCount.textContent = `顯示 ${rows.length} / ${data.count}`;
    const frag = document.createDocumentFragment();

    if (rows.length === 0) {
      const empty = document.createElement("p");
      empty.className = "listed-empty";
      empty.textContent = "未有符合條件嘅最近上市新股";
      frag.appendChild(empty);
      listEl.replaceChildren(frag);
      return;
    }

    rows.forEach((item, index) => {
      const article = document.createElement("article");
      article.className = "listed-row";
      article.style.setProperty("--i", String(index));
      const nameHref = item.info_url || item.quote_url || "#";
      const codeHref = item.quote_url || item.info_url || "#";
      const cash = oneLotCash(item);
      const badge = item.badge
        ? `<span class="badge">${escapeHtml(item.badge)}</span>`
        : "";
      const below = item.badge === "跌穿上市價" ? " is-below" : "";
      article.className = `listed-row${below}`;

      article.innerHTML = `
        <div class="listed-identity">
          <div class="listed-title-row">
            <a class="listed-name" href="${escapeAttr(nameHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.name)}</a>
            <a class="listed-code" href="${escapeAttr(codeHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.code)}.HK</a>
            ${badge}
          </div>
          <p class="listed-date">上市 ${escapeHtml(item.listing_date)}</p>
          <p class="listed-sub">
            招股價 ${escapeHtml(item.offer_price || "—")}
            · 上市價 ${escapeHtml(item.listing_price || "—")}
            · 現價 ${escapeHtml(item.current_price || "—")}
            · 中籤率 ${escapeHtml(item.allotment || "—")}
          </p>
        </div>
        <div class="listed-metrics">
          ${metric("超額倍數", escapeHtml(item.oversub || "—"))}
          ${metric("穩中一手", escapeHtml(item.one_lot || "—"))}
          ${metric("所需資金", escapeHtml(formatCash(cash)))}
          ${metric("首日", escapeHtml(item.first_day || "—"), performanceClass(item.first_day))}
          ${metric("累積", escapeHtml(item.cumulative || "—"), performanceClass(item.cumulative))}
        </div>
      `;
      frag.appendChild(article);
    });

    listEl.replaceChildren(frag);
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

  let searchTimer;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      query = searchInput.value;
      render();
    }, 120);
  });

  if (sortKeyEl) {
    sortKeyEl.addEventListener("change", () => {
      sortKey = sortKeyEl.value;
      render();
    });
  }

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
      label: "最近上市",
    })
    .then((payload) => {
      if (!payload || !Array.isArray(payload.items)) {
        stats.textContent = "無法載入資料";
        return;
      }
      data = payload;
      stats.textContent = `最新一頁 · ${data.count} 隻`;
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
