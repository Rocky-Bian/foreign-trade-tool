let products = [];
let currentProduct = null;
let currentJobId = null;
let pollTimer = null;

const els = {
  productSelect: document.getElementById("productSelect"),
  productDesc: document.getElementById("productDesc"),
  countryGrid: document.getElementById("countryGrid"),
  customerTypeGrid: document.getElementById("customerTypeGrid"),
  selectAllCountries: document.getElementById("selectAllCountries"),
  searchProvider: document.getElementById("searchProvider"),
  fastMode: document.getElementById("fastMode"),
  maxResults: document.getElementById("maxResults"),
  maxQueries: document.getElementById("maxQueries"),
  startBtn: document.getElementById("startBtn"),
  exportBtn: document.getElementById("exportBtn"),
  progressBox: document.getElementById("progressBox"),
  progressFill: document.getElementById("progressFill"),
  progressText: document.getElementById("progressText"),
  emptyState: document.getElementById("emptyState"),
  tableWrap: document.getElementById("tableWrap"),
  resultsBody: document.getElementById("resultsBody"),
  apiStatus: document.getElementById("apiStatus"),
  googleApiKey: document.getElementById("googleApiKey"),
  googleCseId: document.getElementById("googleCseId"),
  saveGoogleBtn: document.getElementById("saveGoogleBtn"),
  googleSaveHint: document.getElementById("googleSaveHint"),
};

function scoreClass(score) {
  if (score >= 70) return "high";
  if (score >= 45) return "mid";
  return "low";
}

function renderChips(container, items) {
  container.innerHTML = "";
  items.forEach((item, idx) => {
    const label = typeof item === "string" ? item : item.name;
    const value = typeof item === "string" ? item : item.code;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (idx < 3 ? " active" : "");
    btn.textContent = label;
    btn.dataset.value = value;
    btn.addEventListener("click", () => btn.classList.toggle("active"));
    container.appendChild(btn);
  });
}

function getSelectedValues(container) {
  return [...container.querySelectorAll(".chip.active")].map((el) => el.dataset.value);
}

function setProductUI() {
  const product = products.find((p) => p.id === els.productSelect.value);
  currentProduct = product;
  if (!product) return;

  els.productDesc.textContent = `${product.name_en} · ${product.description} · 默认市场：${product.market_label}`;
  renderChips(els.countryGrid, product.markets);
  renderChips(els.customerTypeGrid, product.customer_types);
}

async function loadProducts() {
  const res = await fetch("/api/products");
  const data = await res.json();
  products = data.products;

  els.productSelect.innerHTML = products
    .map((p) => `<option value="${p.id}">${p.name}（${p.name_en}）</option>`)
    .join("");

  els.productSelect.addEventListener("change", setProductUI);
  setProductUI();
}

async function loadGoogleSettings() {
  const res = await fetch("/api/settings/google");
  const data = await res.json();
  if (data.google_api_key) els.googleApiKey.value = data.google_api_key;
  if (data.google_cse_id) els.googleCseId.value = data.google_cse_id;
  if (data.configured) {
    els.googleSaveHint.textContent = "✓ Google 搜索已配置，可在上方选择「Google 免费」";
  }
}

async function updateApiStatus() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    els.apiStatus.textContent = cfg.search_provider_label || "DuckDuckGo（免费）";
    els.apiStatus.className = "badge ok";
    if (cfg.is_vercel) {
      els.apiStatus.textContent += " · Vercel";
    }
    if (cfg.google_cse_configured) {
      els.apiStatus.textContent += " · Google 已配置";
    }
    if (cfg.openai_configured) {
      els.apiStatus.textContent += " · OpenAI";
    }
    if (cfg.is_vercel && els.googleSaveHint) {
      els.googleSaveHint.textContent = "Vercel 部署：请在 Vercel 控制台 Environment Variables 中配置 Key";
    }
  } catch {
    els.apiStatus.textContent = "DuckDuckGo（免费）";
    els.apiStatus.className = "badge ok";
  }
}

function showProgress(job) {
  els.progressBox.classList.remove("hidden");
  els.emptyState.classList.add("hidden");

  const total = job.progress.total_steps || job.progress.total_queries || 1;
  const done = job.progress.completed_steps || job.progress.completed_queries || 0;
  const pct = job.progress.status === "completed" ? 100 : Math.min(99, Math.round((done / total) * 100));

  els.progressFill.style.width = `${pct}%`;
  els.progressText.textContent = job.progress.message || job.progress.status;
}

function renderResults(leads) {
  els.resultsBody.innerHTML = leads
    .map(
      (lead) => `
      <tr>
        <td><span class="score ${scoreClass(lead.score)}">${lead.score}</span></td>
        <td>${escapeHtml(lead.company_name)}</td>
        <td><a class="site-link" href="${lead.website}" target="_blank" rel="noopener">${escapeHtml(lead.website)}</a></td>
        <td>${escapeHtml((lead.emails || []).join("; ") || "—")}</td>
        <td>${escapeHtml(lead.customer_type_guess || "—")}</td>
        <td>${escapeHtml(lead.reason || "—")}</td>
      </tr>`
    )
    .join("");

  els.tableWrap.classList.remove("hidden");
  els.exportBtn.classList.remove("hidden");
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function pollJob(jobId) {
  const res = await fetch(`/api/search/${jobId}`);
  const job = await res.json();
  showProgress(job);

  if (job.progress.status === "completed") {
    clearInterval(pollTimer);
    els.startBtn.disabled = false;
    renderResults(job.leads || []);
    return;
  }

  if (job.progress.status === "failed") {
    clearInterval(pollTimer);
    els.startBtn.disabled = false;
    els.progressText.textContent = `失败：${job.error || "未知错误"}`;
  }
}

async function startSearch() {
  if (!currentProduct) return;

  els.startBtn.disabled = true;
  els.exportBtn.classList.add("hidden");
  els.tableWrap.classList.add("hidden");
  els.resultsBody.innerHTML = "";

  const payload = {
    product_id: currentProduct.id,
    countries: getSelectedValues(els.countryGrid),
    customer_types: getSelectedValues(els.customerTypeGrid),
    max_results_per_query: Number(els.maxResults.value),
    max_queries: Number(els.maxQueries.value),
    search_provider: els.searchProvider.value,
    fast_mode: els.fastMode.checked,
  };

  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    els.startBtn.disabled = false;
    alert("启动失败");
    return;
  }

  const job = await res.json();
  currentJobId = job.id;
  showProgress(job);

  if (job.progress.status === "completed") {
    els.startBtn.disabled = false;
    renderResults(job.leads || []);
    return;
  }

  pollTimer = setInterval(() => pollJob(currentJobId), 800);
}

async function saveGoogleSettings() {
  const payload = {
    google_api_key: els.googleApiKey.value.trim(),
    google_cse_id: els.googleCseId.value.trim(),
  };

  const res = await fetch("/api/settings/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    els.googleSaveHint.textContent = err.detail || "保存失败，请检查 Key 和 ID";
    return;
  }

  els.googleSaveHint.textContent = "✓ 已保存！建议选择「Google 免费」搜索引擎";
  els.searchProvider.value = "google_cse";
  await updateApiStatus();
}

els.startBtn.addEventListener("click", startSearch);
els.saveGoogleBtn.addEventListener("click", saveGoogleSettings);

els.selectAllCountries.addEventListener("click", () => {
  els.countryGrid.querySelectorAll(".chip").forEach((chip) => chip.classList.add("active"));
});

els.exportBtn.addEventListener("click", () => {
  if (!currentJobId) return;
  window.location.href = `/api/search/${currentJobId}/export?format=xlsx`;
});

loadProducts();
loadGoogleSettings();
updateApiStatus();
