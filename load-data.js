/** Shared loader: refresh via /api/* when server.py is running; else fall back to static JSON. */
window.loadIpoData = async function loadIpoData({ api, fallback, label }) {
  const stats = document.getElementById("stats");
  const fetched = document.getElementById("fetched");
  if (stats) stats.textContent = `正在更新${label}…`;
  if (fetched) fetched.textContent = "向 AAStocks 拉取最新資料，請稍候";

  try {
    const res = await fetch(api, { cache: "no-store" });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(body || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (apiErr) {
    try {
      const res = await fetch(fallback, { cache: "no-store" });
      if (!res.ok) throw apiErr;
      const data = await res.json();
      if (fetched) {
        fetched.textContent =
          "即時更新失敗，顯示本地快取" +
          (data.fetched_at ? `（${String(data.fetched_at).replace("T", " ")}）` : "");
      }
      return data;
    } catch {
      throw apiErr;
    }
  }
};
