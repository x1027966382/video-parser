/* Video Parser Web UI — 原生 JS，零依赖 */
(function () {
  "use strict";

  let platformSet = {};

  // ── 初始化 ──
  async function init() {
    try {
      let r = await fetch("/api/health");
      let h = await r.json();
      document.getElementById("status").textContent =
        `🟢 在线 · ${h.platforms} 个平台`;
      // 列平台
      r = await fetch("/api/platforms");
      let p = await r.json();
      let tags = document.getElementById("platList");
      platformSet = {};
      (p.platforms || []).forEach((pi) => {
        platformSet[pi.name] = pi;
        tags.innerHTML +=
          `<span class="tag">${pi.name}${pi.needs_cookie ? " 🔑" : ""}</span>`;
      });
      document.getElementById("platCount").textContent =
        Object.keys(platformSet).length;
    } catch (e) {
      document.getElementById("status").textContent = "❌ 连接失败";
    }
  }

  // ── 解析 ──
  window.doParse = async function () {
    let input = document.getElementById("urlInput").value.trim();
    if (!input) return;
    let lines = input.split("\n").filter((l) => l.trim());
    let isBatch = lines.length > 1;
    let res;
    try {
      if (isBatch) {
        res = await fetch("/api/batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ urls: lines }),
        });
      } else {
        res = await fetch("/api/parse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: lines[0] }),
        });
      }
      let data = await res.json();
      renderResults(data, isBatch);
    } catch (e) {
      document.getElementById("status").textContent = "❌ 解析请求失败";
    }
  };

  function renderResults(data, batch) {
    let area = document.getElementById("resultArea");
    area.style.display = "block";
    let cards = document.getElementById("resultCards");
    cards.innerHTML = "";
    if (batch || data.items) {
      let items = data.items || [];
      document.getElementById("resultCount").textContent =
        `✅ ${data.success} 成功 / ${data.failed} 失败`;
      items.forEach((it) => {
        cards.innerHTML += it.success ? card(it) : card(it);
      });
    } else {
      document.getElementById("resultCount").textContent =
        data.success ? "✅ 解析成功" : "❌ 解析失败";
      cards.innerHTML = card(data);
    }
  }

  function card(r) {
    if (!r.success) {
      return `<div class="item fail">❌ ${r.title || "解析失败"}<br><small>${r.source_url || ""}</small></div>`;
    }
    let videoBtn = r.video
      ? `<a class="btn sm" href="/api/download?url=${encodeURIComponent(r.source_url || "")}">⬇ 下载</a>`
      : "";
    let nfoBtn = r.nfo
      ? `<details class="nfo-detail"><summary>📄 NFO</summary><pre>${(r.nfo||"").replace(/</g,"&lt;")}</pre></details>`
      : "";
    return `<div class="item">
      <div class="item-head">
        <span class="platform-badge">${r.platform}</span>
        <strong>${r.title || "无标题"}</strong>
        ${videoBtn}
      </div>
      <div class="item-meta">
        ${r.author ? `<span>作者: ${r.author}</span>` : ""}
        ${r.duration ? `<span>时长: ${r.duration}s</span>` : ""}
        ${r.fingerprint ? `<span title="去重指纹">🔑${r.fingerprint}</span>` : ""}
        ${r.cached ? `<span class="cached">⚡缓存</span>` : ""}
      </div>
      ${r.video ? `<video controls src="${r.proxy_url || r.video}" style="max-width:100%;max-height:300px"></video>` : ""}
      ${r.images && r.images.length ? `<div class="imgs">${r.images.map(u=>`<img src="${u}" style="max-width:200px">`).join("")}</div>` : ""}
      ${nfoBtn}
    </div>`;
  }

  // ── 下载 ──
  window.doDownload = function () {
    let url = document.getElementById("urlInput").value.trim().split("\n")[0];
    if (!url) return;
    window.open("/api/download?url=" + encodeURIComponent(url), "_blank");
  };

  init();
})();