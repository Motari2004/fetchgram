const form = document.getElementById("fetch-form");
const input = document.getElementById("url-input");
const fetchBtn = document.getElementById("fetch-btn");
const errorMsg = document.getElementById("error-msg");
const results = document.getElementById("results");
const template = document.getElementById("result-template");

function setLoading(isLoading) {
  fetchBtn.disabled = isLoading;
  fetchBtn.querySelector(".btn-label").textContent = isLoading ? "Fetching…" : "Fetch";
  fetchBtn.querySelector(".btn-spinner").hidden = !isLoading;
}

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.hidden = false;
}

function clearError() {
  errorMsg.hidden = true;
  errorMsg.textContent = "";
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return "";
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${String(rem).padStart(2, "0")}`;
}

function renderResults(items, sourceUrl) {
  results.innerHTML = "";
  results.hidden = false;

  items.forEach((item) => {
    const node = template.content.cloneNode(true);

    const img = node.querySelector(".thumb img");
    if (item.thumbnail) {
      img.src = item.thumbnail;
      img.alt = item.title || "Video thumbnail";
    } else {
      img.closest(".thumb").style.display = "none";
    }

    node.querySelector(".meta-title").textContent = item.title || "Instagram video";

    const uploaderEl = node.querySelector(".uploader");
    const durationEl = node.querySelector(".duration");
    const dotEl = node.querySelector(".dot");

    uploaderEl.textContent = item.uploader ? `@${item.uploader}` : "";
    const dur = formatDuration(item.duration);
    durationEl.textContent = dur;

    if (!item.uploader || !dur) dotEl.style.display = "none";

    const dlBtn = node.querySelector(".dl-btn");
    const params = new URLSearchParams({ url: sourceUrl, id: item.id || "" });
    dlBtn.href = `/api/download?${params.toString()}`;

    results.appendChild(node);
  });
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  results.hidden = true;

  const url = input.value.trim();
  if (!url) return;

  setLoading(true);
  try {
    const res = await fetch("/api/fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || "Something went wrong. Try again.");
      return;
    }

    renderResults(data.items, data.source_url);
  } catch (err) {
    showError("Couldn't reach the server. Check your connection and try again.");
  } finally {
    setLoading(false);
  }
});
