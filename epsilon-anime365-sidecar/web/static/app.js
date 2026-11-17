const form = document.querySelector("#config-form");
const saveButton = document.querySelector("#save-button");
const saveResult = document.querySelector("#save-result");
const restartNotice = document.querySelector("#restart-notice");
let secretSet = {};
let loaded = false;
let dirty = false;

const statusCopy = {
  configuration_required: [
    "bad",
    "Требуется настройка",
    "Заполните обязательные поля и сохраните настройки.",
  ],
  restart_required: [
    "warn",
    "Требуется перезапуск",
    "Примените сохранённые настройки перезапуском приложения в Umbrel.",
  ],
  configured: [
    "good",
    "Настройки заполнены",
    "Статистика появится после создания медиатеки. Состояние sidecar доступно в Umbrel.",
  ],
  library_detected: [
    "good",
    "Медиатека обнаружена",
    "Показаны данные манифеста. Состояние sidecar доступно в Umbrel.",
  ],
};
const cleanupCopy = {
  do_not_delete:
    "Серии остаются в медиатеке независимо от статуса просмотра. Задержка ниже используется только при включённом удалении по статусу.",
  delete_watched_episodes:
    "Просмотр определяется по номеру последней просмотренной серии в списках Anime 365. Удалённые серии не загружаются повторно, даже если тайтл указан явно. Активное воспроизведение откладывает удаление.",
  delete_completed_and_dropped_shows:
    "Удаляются серии просмотренных и брошенных сериалов, а также сериалов вне всех списков Anime 365. «Смотрю», «Запланировано» и «Отложено» сохраняются. Очистка начнётся после успешной синхронизации списков. Удалённые серии не загружаются повторно; активное воспроизведение откладывает удаление.",
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

function setMessage(text, kind = "") {
  saveResult.textContent = text;
  saveResult.className = `save-result ${kind}`;
}

function describeError(error) {
  return error.message.replace(
    /\b[a-z][a-z_]+\b/g,
    (name) => form.querySelector(`label[for="${name}"]`)?.textContent || name,
  );
}

function collectForm() {
  const payload = {};
  for (const element of form.elements) {
    if (!element.name || element.matches(":disabled") || element.readOnly)
      continue;
    payload[element.name] =
      element.type === "checkbox" ? element.checked : element.value;
  }
  payload._clear_secrets = [
    ...form.querySelectorAll("[data-clear-secret]:checked"),
  ]
    .filter((element) => !element.matches(":disabled"))
    .map((element) => element.dataset.clearSecret);
  return payload;
}

function updateConditions() {
  const provider = form.elements.media_server.value;
  for (const fieldset of form.querySelectorAll("[data-provider]")) {
    const inactive = fieldset.dataset.provider !== provider;
    fieldset.hidden = inactive;
    fieldset.disabled = inactive;
  }
  for (const element of form.querySelectorAll("[data-secret]")) {
    const clear = form.querySelector(`[data-clear-secret="${element.name}"]`);
    element.disabled = Boolean(clear?.checked);
    element.required =
      !secretSet[element.name] &&
      ["anime365_password", `${provider}_api_key`].includes(element.name);
  }
  const policy = form.elements.watched_episodes_cleanup_policy.value;
  document.querySelector("#cleanup-description").textContent =
    cleanupCopy[policy] || "";
}

function populateForm(config, savedSecrets) {
  secretSet = savedSecrets;
  for (const [name, value] of Object.entries(config)) {
    const element = form.elements.namedItem(name);
    if (!element) continue;
    if (element.type === "checkbox")
      element.checked = String(value).toLowerCase() === "true";
    else element.value = value ?? "";
  }
  for (const [name, isSet] of Object.entries(savedSecrets)) {
    const element = form.elements.namedItem(name);
    if (!element) continue;
    const hint = element.parentElement.querySelector(".secret-hint");
    hint.textContent = isSet
      ? "Сохранено. Оставьте пустым, чтобы сохранить, или введите новое значение."
      : "";
    element.placeholder = isSet
      ? "Сохранённое значение скрыто"
      : element.dataset.originalPlaceholder || "Введите значение";
    const clear = form.querySelector(`[data-clear-secret="${name}"]`);
    clear.checked = false;
    // Required credentials are replaced by entering a new value; optional integrations can be disabled.
    clear.parentElement.classList.toggle(
      "hidden",
      !isSet ||
        ["anime365_password", "emby_api_key", "jellyfin_api_key"].includes(
          name,
        ),
    );
  }
  updateConditions();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
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
    document.querySelector("#status-dot").className = `status-dot ${copy[0]}`;
    document.querySelector("#status-label").textContent = payload.configured
      ? "Настройки сохранены"
      : "Первое подключение";
    document.querySelector("#status-title").textContent = copy[1];
    document.querySelector("#status-note").textContent = copy[2];
    document.querySelector("#shows-count").textContent = payload.library.shows;
    document.querySelector("#episodes-count").textContent =
      payload.library.episodes;
    document.querySelector("#translations-count").textContent =
      `${payload.library.translations} переводов`;
    document.querySelector("#disk-free").textContent = formatBytes(
      payload.library.disk_free,
    );
    document.querySelector("#manifest-updated").textContent = payload.library
      .manifest_updated_at
      ? `Медиатека обновлена: ${new Date(payload.library.manifest_updated_at).toLocaleString("ru-RU")}`
      : "Медиатека ещё не создана";
    restartNotice.classList.toggle("hidden", !payload.restart_required);
  } catch (error) {
    document.querySelector("#status-title").textContent =
      "Не удалось получить статус";
    document.querySelector("#status-note").textContent = error.message;
    document.querySelector("#status-dot").className = "status-dot bad";
  }
}

form.addEventListener("input", () => {
  if (!loaded) return;
  dirty = true;
  setMessage("Есть несохранённые изменения");
});
form.addEventListener("change", updateConditions);
window.addEventListener("beforeunload", (event) => {
  if (dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!loaded || !form.reportValidity()) return;
  const config = collectForm();
  saveButton.disabled = true;
  form.inert = true;
  form.setAttribute("aria-busy", "true");
  setMessage("Сохраняем…");
  try {
    const payload = await api("/api/config", {
      method: "POST",
      body: JSON.stringify(config),
    });
    // Erase entered credentials immediately after a successful save, even if reload fails.
    for (const element of form.querySelectorAll("[data-secret]"))
      element.value = "";
    dirty = false;
    setMessage(payload.message, "good");
    restartNotice.classList.remove("hidden");
    await loadConfig();
    await loadStatus();
  } catch (error) {
    setMessage(describeError(error), "bad");
  } finally {
    form.inert = false;
    form.setAttribute("aria-busy", "false");
    saveButton.disabled = false;
  }
});

for (const button of document.querySelectorAll(".test-button")) {
  button.addEventListener("click", async () => {
    const service = button.dataset.test;
    const result = document.querySelector(`[data-result="${service}"]`);
    button.disabled = true;
    result.textContent = "Проверяем…";
    result.className = "test-result";
    try {
      const payload = await api(`/api/test/${service}`, {
        method: "POST",
        body: JSON.stringify(collectForm()),
      });
      result.textContent = payload.message;
      result.classList.add("good");
    } catch (error) {
      result.textContent = describeError(error);
      result.classList.add("bad");
    } finally {
      button.disabled = false;
    }
  });
}

document.querySelector("#refresh-status").addEventListener("click", loadStatus);
const navLinks = [...document.querySelectorAll('.section-nav a[href^="#"]')];
let scrollScheduled = false;
window.addEventListener(
  "scroll",
  () => {
    if (scrollScheduled) return;
    scrollScheduled = true;
    requestAnimationFrame(() => {
      const threshold = window.innerWidth <= 820 ? 100 : 60;
      const current =
        [...navLinks]
          .reverse()
          .find(
            (link) =>
              document.querySelector(link.hash).getBoundingClientRect().top <=
              threshold,
          ) || navLinks[0];
      for (const link of navLinks) {
        if (link === current) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      }
      scrollScheduled = false;
    });
  },
  { passive: true },
);
for (const element of form.querySelectorAll("[data-secret]"))
  element.dataset.originalPlaceholder = element.placeholder;
form.inert = true;
loadConfig()
  .then(() => {
    loaded = true;
    saveButton.disabled = false;
    form.inert = false;
    form.setAttribute("aria-busy", "false");
    setMessage("Настройки загружены");
  })
  .catch((error) =>
    setMessage(
      `Не удалось загрузить настройки: ${error.message}. Обновите страницу.`,
      "bad",
    ),
  );
loadStatus();
setInterval(loadStatus, 30000);
