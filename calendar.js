(() => {
  const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];
  const MONTHS = [
    "一月",
    "二月",
    "三月",
    "四月",
    "五月",
    "六月",
    "七月",
    "八月",
    "九月",
    "十月",
    "十一月",
    "十二月",
  ];

  function parseISO(s) {
    const [y, m, d] = s.split("-").map(Number);
    return new Date(y, m - 1, d);
  }

  function fmtISO(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
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

  function hasOversub(item) {
    return (
      item.oversub_primary &&
      item.oversub_primary !== "尚未見報道" &&
      item.oversub_primary !== "尚未公布"
    );
  }

  function boot(data) {
    document.getElementById("stats").textContent =
      `未來 30 日有 ${data.count} 隻招股截止`;
    document.getElementById("fetched").textContent = data.fetched_at
      ? `更新於 ${data.fetched_at.replace("T", " ")}`
      : "";
    if (data._refresh_error) {
      document.getElementById("fetched").textContent += "（部分更新失敗，已用快取）";
    }
    document.getElementById("window").textContent =
      `${data.as_of} → ${data.window_end}`;
    if (data.note) document.getElementById("note").textContent = data.note;

    const byDate = new Map();
    for (const item of data.items) {
      const key = item.deadline_iso || item.listing_date_iso;
      if (!key) continue;
      if (!byDate.has(key)) byDate.set(key, []);
      byDate.get(key).push(item);
    }

    const start = parseISO(data.as_of);
    const end = parseISO(data.window_end);

    const months = [];
    let cursor = new Date(start.getFullYear(), start.getMonth(), 1);
    const lastMonth = new Date(end.getFullYear(), end.getMonth(), 1);
    while (cursor <= lastMonth) {
      months.push(new Date(cursor));
      cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
    }

    const calendars = document.getElementById("calendars");
    const frag = document.createDocumentFragment();

    for (const monthStart of months) {
      const y = monthStart.getFullYear();
      const m = monthStart.getMonth();
      const daysInMonth = new Date(y, m + 1, 0).getDate();
      const firstDow = new Date(y, m, 1).getDay();

      const section = document.createElement("section");
      section.className = "cal-month";
      section.innerHTML = `<h2 class="cal-month-title">${y} ${MONTHS[m]}</h2>`;

      const grid = document.createElement("div");
      grid.className = "cal-grid";
      grid.setAttribute("role", "grid");
      grid.setAttribute("aria-label", `${y} ${MONTHS[m]}`);

      for (const w of WEEKDAYS) {
        const head = document.createElement("div");
        head.className = "cal-dow";
        head.textContent = w;
        grid.appendChild(head);
      }

      for (let i = 0; i < firstDow; i++) {
        const empty = document.createElement("div");
        empty.className = "cal-day is-pad";
        empty.setAttribute("aria-hidden", "true");
        grid.appendChild(empty);
      }

      for (let day = 1; day <= daysInMonth; day++) {
        const cellDate = new Date(y, m, day);
        const iso = fmtISO(cellDate);
        const inWindow = cellDate >= start && cellDate <= end;
        const isToday = iso === data.as_of;
        const events = byDate.get(iso) || [];

        const cell = document.createElement("div");
        cell.className = "cal-day";
        if (!inWindow) cell.classList.add("is-out");
        if (isToday) cell.classList.add("is-today");
        if (events.length) cell.classList.add("has-ipo");

        let body = `<div class="cal-daynum">${day}</div>`;
        if (events.length) {
          body += `<ul class="cal-events">`;
          for (const ev of events) {
            const hot = hasOversub(ev);
            const href = ev.info_url || "#";
            body += `<li class="cal-event ${hot ? "is-hot" : ""}">
              <a href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer">
                <span class="cal-name">${escapeHtml(ev.name)}</span>
                <span class="cal-code">${escapeHtml(ev.code)}.HK</span>
                <span class="cal-oversub">${escapeHtml(ev.oversub_primary)}</span>
              </a>
            </li>`;
          }
          body += `</ul>`;
        } else if (inWindow) {
          body += `<div class="cal-empty">—</div>`;
        }

        cell.innerHTML = body;
        grid.appendChild(cell);
      }

      section.appendChild(grid);
      frag.appendChild(section);
    }

    calendars.replaceChildren(frag);

    const listBody = document.getElementById("list-body");
    const listFrag = document.createDocumentFragment();
    if (data.items.length === 0) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        '<td colspan="7" class="empty-row">未來 30 日暫時未見招股截止嘅新股</td>';
      listFrag.appendChild(tr);
    } else {
      for (const item of data.items) {
        const tr = document.createElement("tr");
        const href = item.info_url || "#";
        const newsBits = (item.news || [])
          .map(
            (n) =>
              `${escapeHtml(n.display)}（${escapeHtml(n.note)}）`
          )
          .join("； ");
        tr.innerHTML = `
          <td class="txt-l num">${escapeHtml(item.deadline_iso || item.deadline || "—")}</td>
          <td class="txt-l">
            <div class="name-cell">
              <a href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.name)}</a>
              <span class="code">${escapeHtml(item.code)}.HK</span>
            </div>
          </td>
          <td class="txt-l"><span class="status-pill status-live">${escapeHtml(item.status || "即將上市")}</span></td>
          <td class="num ${hasOversub(item) ? "pos" : "muted"}">${escapeHtml(item.oversub_primary)}</td>
          <td class="txt-l">${escapeHtml(item.oversub_note)}${newsBits ? `<div class="muted small">${newsBits}</div>` : ""}</td>
          <td class="num">${escapeHtml(item.entry_fee || "—")}</td>
          <td class="num">${escapeHtml(item.listing_date_iso || item.listing_date || "—")}</td>
        `;
        listFrag.appendChild(tr);
      }
    }
    listBody.replaceChildren(listFrag);
  }

  window
    .loadIpoData({
      api: "/api/calendar",
      fallback: "calendar-data.json",
      label: "IPO 月曆",
    })
    .then((payload) => {
      if (!payload || !Array.isArray(payload.items)) {
        document.getElementById("stats").textContent = "無法載入資料";
        return;
      }
      boot(payload);
    })
    .catch((err) => {
      document.getElementById("stats").textContent = "無法載入資料";
      document.getElementById("fetched").textContent = String(
        err.message || err
      );
    });
})();
