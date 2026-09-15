const form = document.querySelector("#form");
const result = document.querySelector("#result");
const saveButton = document.querySelector("#save");
const restartNotice = document.querySelector("#restart-notice");

const states = {
  configuration_required: ["bad", "Не настроено", "Добавьте параметры Site из Pangolin."],
  restart_required: ["warn", "Требуется перезапуск", "Конфигурация сохранена, но Newt ещё не перечитал её."],
  connecting: ["warn", "Ожидание туннеля", "Проверьте ID, secret и журнал Newt, если состояние долго не меняется."],
  connected: ["good", "Туннель подключён", "Newt установил соединение с Pangolin."],
};

async function api(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function collect() {
  const payload = {};
  for (const element of form.elements) {
    if (!element.name) continue;
    payload[element.name] = element.type === "checkbox" ? element.checked : element.value;
  }
  return payload;
}

async function loadConfig() {
  const payload = await api("/api/config");
  for (const [name, value] of Object.entries(payload.config)) {
    const element = form.elements.namedItem(name);
    if (!element) continue;
    if (element.type === "checkbox") element.checked = Boolean(value);
    else element.value = value ?? "";
  }
  const secret = form.elements.namedItem("secret");
  secret.required = !payload.secret_set;
  document.querySelector("#secret-hint").textContent = payload.secret_set ? "Secret уже сохранён. Оставьте поле пустым, чтобы не менять его." : "";
}

async function loadState() {
  try {
    const payload = await api("/api/state");
    const copy = states[payload.state] || states.configuration_required;
    const card = document.querySelector("#status-card");
    card.className = `status ${copy[0]}`;
    document.querySelector("#status-label").textContent = payload.configured ? "Конфигурация сохранена" : "Требуется конфигурация";
    document.querySelector("#status-title").textContent = copy[1];
    document.querySelector("#status-note").textContent = copy[2];
    restartNotice.classList.toggle("hidden", !payload.restart_required);
  } catch (error) {
    result.textContent = error.message;
    result.className = "bad";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  saveButton.disabled = true;
  result.textContent = "Сохраняем…";
  result.className = "";
  try {
    const payload = await api("/api/config", { method: "POST", body: JSON.stringify(collect()) });
    result.textContent = payload.message;
    result.className = "good";
    await loadConfig();
    await loadState();
  } catch (error) {
    result.textContent = error.message;
    result.className = "bad";
  } finally {
    saveButton.disabled = false;
  }
});

document.querySelector("#test").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const payload = await api("/api/test", { method: "POST", body: JSON.stringify(collect()) });
    result.textContent = payload.message;
    result.className = "good";
  } catch (error) {
    result.textContent = error.message;
    result.className = "bad";
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#refresh").addEventListener("click", loadState);
Promise.all([loadConfig(), loadState()]).catch((error) => { result.textContent = error.message; result.className = "bad"; });
setInterval(loadState, 30000);
