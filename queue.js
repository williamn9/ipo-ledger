(() => {
  const tbody = document.getElementById("tbody");
  const searchInput = document.getElementById("search");
  const statusFilter = document.getElementById("status-filter");
  const visibleCount = document.getElementById("visible-count");
  const stats = document.getElementById("stats");
  const fetched = document.getElementById("fetched");
  const note = document.getElementById("note");

  let data = null;
  let sortKey = "listing_date";
  let sortDir = "asc";
  let query = "";

  function parseNumber(value) {
    if (value == null) return NaN;
    const raw = String(value).trim();
    if (
      !raw ||
      raw === "N/A" ||
      raw === "—" ||
      raw === "尚未公布" ||
      raw === "認購不足"
    ) {
      return NaN;
    }
    const cleaned = raw
      .replace(/,/g, "")
      .replace(/%/g, "")
      .replace(/手/g, "")
      .replace(/^\+/, "");
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : NaN;
  }

  function compare(a, b, key) {
    if (key === "name" || key === "industry" || key === "status") {
      return String(a[key] || "").localeCompare(String(b[key] || ""), "zh-Hant");
    }
    if (key === "listing_date" || key === "deadline") {
      return String(a[key] || "").localeCompare(String(b[key] || ""));
    }
    const na = parseNumber(a[key]);
    const nb = parseNumber(b[key]);
    if (Number.isNaN(na) && Number.isNaN(nb)) return 0;
    if (Number.isNaN(na)) return 1;
    if (Number.isNaN(nb)) return -1;
    return na - nb;
  }

  function statusClass(status) {
    if (status === "正在招股") return "status-live";
    if (status === "已截止・待上市") return "status-closed";
    return "status-soon";
  }

  function oversubHtml(value) {
    const raw = String(value ?? "尚未公布");
    if (raw === "尚未公布" || raw === "—" || raw === "N/A") {
      return `<span class="muted">${escapeHtml(raw)}</span>`;
    }
    if (raw === "認購不足") {
      return `<span class="neg">${escapeHtml(raw)}</span>`;
    }
    const n = parseNumber(raw);
    if (!Number.isNaN(n) && n >= 100) {
      return `<span class="pos num">${escapeHtml(raw)}</span>`;
    }
    return `<span class="num">${escapeHtml(raw)}</span>`;
  }

  function filteredSorted() {
    const q = query.trim().toLowerCase();
    const status = statusFilter.value;
    let rows = data.items.filter((item) => {
      if (status !== "all" && item.status !== status) return false;
      if (!q) return true;
      return (
        item.name.toLowerCase().includes(q) ||
        String(item.code).toLowerCase().includes(q) ||
        String(item.industry || "")
          .toLowerCase()
          .includes(q)
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

    if (rows.length === 0) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td colspan="10" class="empty-row">而家未有符合條件嘅排隊新股</td>`;
      frag.appendChild(tr);
      tbody.replaceChildren(frag);
      return;
    }

    for (const item of rows) {
      const tr = document.createElement("tr");
      const href = item.info_url || "#";
      const badge = item.badge
        ? `<span class="badge">${escapeHtml(item.badge)}</span>`
        : "";
      tr.innerHTML = `
        <td class="txt-l"><span class="status-pill ${statusClass(item.status)}">${escapeHtml(item.status)}</span></td>
        <td class="txt-l">
          <div class="name-cell">
            <a href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.name)}</a>
            <span class="code">${escapeHtml(item.code ? item.code + ".HK" : "")}</span>
            ${badge}
          </div>
        </td>
        <td class="txt-l">${escapeHtml(item.industry || "—")}</td>
        <td class="num">${escapeHtml(item.offer_price || "—")}</td>
        <td>${oversubHtml(item.oversub)}</td>
        <td class="num">${escapeHtml(item.allotment || "—")}</td>
        <td class="num">${escapeHtml(item.one_lot || "—")}</td>
        <td class="num">${escapeHtml(item.entry_fee || "—")}</td>
        <td class="num">${escapeHtml(item.deadline || "—")}</td>
        <td class="num">${escapeHtml(item.listing_date || "—")}</td>
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
        sortDir =
          key === "name" || key === "industry" || key === "listing_date"
            ? "asc"
            : "desc";
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
  statusFilter.addEventListener("change", render);

  window
    .loadIpoData({
      api: "/api/queue",
      fallback: "queue-data.json",
      label: "排隊上市",
    })
    .then((payload) => {
      if (!payload || !Array.isArray(payload.items)) {
        stats.textContent = "無法載入資料";
        return;
      }
      data = payload;
      stats.textContent = `排隊 ${data.count} 間（招股中 ${data.offering_count} · 其他 ${data.pending_count}）`;
      fetched.textContent = data.fetched_at
        ? `更新於 ${data.fetched_at.replace("T", " ")}`
        : "";
      if (data.note) note.textContent = data.note;
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
