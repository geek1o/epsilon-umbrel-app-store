const form = document.querySelector("#config-form");
const saveButton = document.querySelector("#save-button");
const saveResult = document.querySelector("#save-result");
const restartNotice = document.querySelector("#restart-notice");

const statusCopy = {
  configuration_required: ["bad", "Требуется настройка", "Заполните обязательные поля и сохраните конфигурацию."],
  restart_required: ["warn", "Требуется перезапуск", "Настройки изменены и ещё не применены к upstream-контейнеру."],
  configured: ["good", "Конфигурация готова", "После запуска sidecar здесь появится статистика его manifest.json."],
  library_detected: ["good", "Медиатека обнаружена", "Sidecar уже создавал manifest.json в общей папке Emby."],
};

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  const units = ["Б", "КБ", "МБ", "ГБ", "ТБ"];
  let value = Number(bytes);
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 || unit === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unit]}`;
}

function formatDate(value) {
  if (!value) return "медиатека ещё не создана";
  return `manifest: ${new Date(value).toLocaleString("ru-RU")}`;
}

function setMessage(text, kind = "") {
  saveResult.textContent = text;
  saveResult.className = `save-result ${kind}`;
}

function collectForm() {
  const payload = {};
  for (const element of form.elements) {
    if (!element.name) continue;
    payload[element.name] = element.type === "checkbox" ? element.checked : element.value;
  }
  return payload;
}

function populateForm(config, secretSet) {
  for (const [name, value] of Object.entries(config)) {
    const element = form.elements.namedItem(name);
    if (!element) continue;
    if (element.type === "checkbox") {
      element.checked = String(value).toLowerCase() === "true";
    } else {
      element.value = value ?? "";
    }
  }
  for (const [name, isSet] of Object.entries(secretSet)) {
    const element = form.elements.namedItem(name);
    if (!element) continue;
    element.required = !isSet && ["anime365_password", "emby_api_key"].includes(name);
    const hint = element.parentElement.querySelector(".secret-hint");
    if (hint) hint.classList.toggle("set", Boolean(isSet));
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

async function loadConfig() {
  const payload = await api("/api/config");
  populateForm(payload.config, payload.secret_set);
}

async function loadStatus() {
  try {
    const payload = await api("/api/status");
    const copy = statusCopy[payload.state] || statusCopy.configuration_required;
    const dot = document.querySelector("#status-dot");
    dot.className = `status-dot ${copy[0]}`;
    document.querySelector("#status-label").textContent = payload.configured ? "Настроено" : "Не настроено";
    document.querySelector("#status-title").textContent = copy[1];
    document.querySelector("#status-note").textContent = copy[2];
    document.querySelector("#shows-count").textContent = payload.library.shows;
    document.querySelector("#episodes-count").textContent = payload.library.episodes;
    document.querySelector("#translations-count").textContent = `${payload.library.translations} переводов`;
    document.querySelector("#disk-free").textContent = formatBytes(payload.library.disk_free);
    document.querySelector("#manifest-updated").textContent = formatDate(payload.library.manifest_updated_at);
    restartNotice.classList.toggle("hidden", !payload.restart_required);
  } catch (error) {
    document.querySelector("#status-title").textContent = "Панель недоступна";
    document.querySelector("#status-note").textContent = error.message;
    document.querySelector("#status-dot").className = "status-dot bad";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  saveButton.disabled = true;
  setMessage("Сохраняем…");
  try {
    const payload = await api("/api/config", { method: "POST", body: JSON.stringify(collectForm()) });
    setMessage(payload.message, "good");
    restartNotice.classList.remove("hidden");
    await loadConfig();
    await loadStatus();
  } catch (error) {
    setMessage(error.message, "bad");
  } finally {
    saveButton.disabled = false;
  }
});

for (const button of document.querySelectorAll(".test-button")) {
  button.addEventListener("click", async () => {
    const service = button.dataset.test;
    button.disabled = true;
    const previous = button.textContent;
    button.textContent = "Проверяем…";
    setMessage("");
    try {
      const payload = await api(`/api/test/${service}`, { method: "POST", body: JSON.stringify(collectForm()) });
      setMessage(payload.message, "good");
    } catch (error) {
      setMessage(error.message, "bad");
    } finally {
      button.disabled = false;
      button.textContent = previous;
    }
  });
}

document.querySelector("#refresh-status").addEventListener("click", loadStatus);

Promise.all([loadConfig(), loadStatus()]).catch((error) => setMessage(error.message, "bad"));
setInterval(loadStatus, 30000);
