'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const form = $('#settings-form');
const kinds = ['plex', 'jellyfin', 'emby'];
const labels = {plex: 'Plex', jellyfin: 'Jellyfin', emby: 'Emby'};
const bools = ['enabled', 'dryrun', 'generate_guids', 'generate_locations', 'ssl_bypass'];
const numbers = ['interval', 'request_timeout', 'max_threads'];
const filters = ['whitelist_users', 'blacklist_users', 'whitelist_library', 'blacklist_library', 'whitelist_library_type', 'blacklist_library_type'];
let currentState = null, dirty = false, busy = false, loaded = false;
let activeTab = 'servers';

function notify(message, error = false) {
  const box = $('#message'); box.textContent = message; box.className = error ? 'notice error' : 'notice'; box.hidden = false;
}
function markDirty() {
  dirty = true; $('#dirty-dot').hidden = false;
  $('#save-status').textContent = 'Есть несохранённые изменения';
}
async function api(path, payload) {
  const options = payload === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-JPW-Request': '1'}, body: JSON.stringify(payload)};
  const response = await fetch(path, {...options, cache: 'no-store'});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Не удалось выполнить запрос.');
  return value;
}
function makeDirections() {
  const table = document.createElement('table'); table.className = 'direction-table';
  const head = document.createElement('tr');
  for (const label of ['Из ↓ / В →', ...kinds.map(k => labels[k])]) { const th = document.createElement('th'); th.textContent = label; head.append(th); }
  const thead = document.createElement('thead'); thead.append(head); table.append(thead);
  const body = document.createElement('tbody');
  for (const source of kinds) {
    const row = document.createElement('tr'), th = document.createElement('th'); th.scope = 'row'; th.textContent = labels[source]; row.append(th);
    for (const target of kinds) {
      const cell = document.createElement('td'), input = document.createElement('input'); input.type = 'checkbox'; input.name = `direction_${source}_to_${target}`; input.checked = true;
      input.setAttribute('aria-label', `${labels[source]} → ${labels[target]}`); cell.append(input); row.append(cell);
    }
    body.append(row);
  }
  table.append(body); $('#directions').append(table);
}
function serverPayload(card) {
  return {id: card.dataset.id, ...Object.fromEntries(['kind', 'name', 'url', 'token'].map(key => [key, $(`[data-field="${key}"]`, card).value.trim()]))};
}
function renumber() {
  $$('.server-card').forEach((card, index) => { $('.server-number', card).textContent = `СЕРВЕР ${String(index + 1).padStart(2, '0')}`; });
  $('#empty-state').hidden = $$('.server-card').length > 0;
}
function addServer(server = {}) {
  const card = $('#server-template').content.firstElementChild.cloneNode(true);
  // UUID generation needs no secure browser context on Umbrel's HTTP LAN address.
  card.dataset.id = server.id || `server_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  for (const key of ['kind', 'name', 'url', 'token']) $(`[data-field="${key}"]`, card).value = server[key] || (key === 'kind' ? 'plex' : '');
  card.dataset.savedKind = server.kind || '';
  const token = $('[data-field="token"]', card);
  token.required = !server.token_set;
  if (server.token_set) { token.placeholder = 'Сохранён · оставь пустым, чтобы не менять'; $('.token-hint', card).textContent = 'Токен сохранён. Введи новый, чтобы заменить его.'; }
  function updateKind() {
    const kind = $('[data-field="kind"]', card).value;
    $('.server-kind', card).textContent = labels[kind].toUpperCase();
    $('[data-field="url"]', card).placeholder = kind === 'plex' ? 'http://192.168.1.10:32400' : kind === 'emby' ? 'http://epsilon-emby_server_1:8096/emby' : 'http://192.168.1.10:8096';
    token.required = !server.token_set || kind !== card.dataset.savedKind;
    if (kind !== card.dataset.savedKind) token.placeholder = 'Введите токен';
    else if (server.token_set) token.placeholder = 'Сохранён · оставь пустым, чтобы не менять';
  }
  updateKind();
  $('[data-field="kind"]', card).addEventListener('change', updateKind);
  $('.remove-server', card).addEventListener('click', () => { card.remove(); renumber(); markDirty(); });
  $('.test-server', card).addEventListener('click', async event => {
    const button = event.currentTarget, result = $('.test-result', card);
    button.disabled = true; result.textContent = 'Проверяем доступ и токен…'; result.className = 'test-result';
    try { const response = await api('/api/test', serverPayload(card)); result.textContent = response.message; result.className = 'test-result ok'; }
    catch (error) { result.textContent = error.message; result.className = 'test-result error'; }
    finally { button.disabled = false; }
  });
  card.addEventListener('input', () => { $('.test-result', card).textContent = 'Параметры изменены · проверь подключение'; $('.test-result', card).className = 'test-result'; });
  $('#servers').append(card); renumber();
}
function readForm() {
  const value = {servers: $$('.server-card').map(serverPayload), directions: {}};
  for (const key of bools) value[key] = form.elements[key].checked;
  for (const key of numbers) value[key] = Number(form.elements[key].value);
  value.debug_level = form.elements.debug_level.value;
  for (const source of kinds) for (const target of kinds) value.directions[`${source}_to_${target}`] = form.elements[`direction_${source}_to_${target}`].checked;
  for (const key of ['user_mapping', 'library_mapping']) {
    try { value[key] = JSON.parse(form.elements[key].value || '{}'); }
    catch { throw new Error(`Проверь JSON в поле «${key === 'user_mapping' ? 'Имена пользователей' : 'Названия библиотек'}».`); }
  }
  for (const key of filters) value[key] = form.elements[key].value.split(',').map(v => v.trim()).filter(Boolean);
  return value;
}
function fillForm(config) {
  $('#servers').replaceChildren(); config.servers.forEach(addServer); renumber();
  for (const key of bools) form.elements[key].checked = config[key];
  for (const key of numbers) form.elements[key].value = config[key];
  form.elements.debug_level.value = config.debug_level;
  for (const source of kinds) for (const target of kinds) form.elements[`direction_${source}_to_${target}`].checked = config.directions[`${source}_to_${target}`];
  for (const key of ['user_mapping', 'library_mapping']) form.elements[key].value = JSON.stringify(config[key], null, 2);
  for (const key of filters) form.elements[key].value = config[key].join(', ');
}
function date(timestamp) { return timestamp ? new Date(timestamp * 1000).toLocaleString('ru-RU', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'}) : ''; }
function renderStatus(state) {
  currentState = state;
  const {config, status} = state, chip = $('#status-chip');
  $('#version').textContent = state.version;
  $('#server-count').replaceChildren(document.createTextNode(String(config.servers.length)), Object.assign(document.createElement('small'), {textContent: 'сохранено'}));
  const runDry = status.running ? status.running_dryrun : config.dryrun;
  $('#mode-label').replaceChildren(document.createTextNode(runDry ? 'Проверка' : 'Синхронизация'), Object.assign(document.createElement('small'), {textContent: runDry ? 'без изменений' : 'с записью на серверы'}));
  const resultLabels = {success: 'Завершён', error: 'Ошибка', interrupted: 'Прерван'};
  $('#last-run').replaceChildren(document.createTextNode(status.last_finished_at ? (resultLabels[status.last_result] || 'Завершён') : 'Ещё не было'));
  if (status.last_finished_at) $('#last-run').append(Object.assign(document.createElement('small'), {textContent: date(status.last_finished_at) + (status.last_dryrun ? ' · проверка' : '')}));
  $('#next-run').textContent = status.running ? (config.enabled ? 'После текущего запуска' : 'Расписание выключено') : config.enabled ? date(status.next_at) || 'Скоро' : 'Расписание выключено';
  chip.className = 'status-chip';
  if (status.config_error) { chip.textContent = 'Ошибка настроек'; chip.classList.add('error'); }
  else if (status.running) { chip.textContent = runDry ? 'Идёт проверка' : 'Идёт синхронизация'; chip.classList.add('running'); }
  else if (!state.ready) chip.textContent = 'Нужна настройка';
  else if (status.last_result === 'error') { chip.textContent = 'Ошибка последнего запуска'; chip.classList.add('error'); }
  else chip.textContent = config.enabled ? 'По расписанию' : 'Расписание выключено';
  $('#run-now').disabled = busy || status.running || !loaded;
}
async function refreshLogs() { try { $('#log-output').textContent = (await api('/api/logs')).text; } catch (error) { notify(error.message, true); } }
function switchTab(tab) {
  activeTab = tab;
  $$('.nav-item').forEach(button => { const active = button.dataset.tab === tab; button.classList.toggle('active', active); button.setAttribute('aria-selected', String(active)); });
  $$('.tab-panel').forEach(panel => { panel.hidden = panel.id !== `tab-${tab}`; });
  if (tab === 'logs') refreshLogs();
}
function validateVisibleForm() {
  const invalid = $$('input,select,textarea', form).find(input => !input.checkValidity());
  if (!invalid) return true;
  const panel = invalid.closest('.tab-panel'); if (panel) switchTab(panel.id.replace('tab-', ''));
  const details = invalid.closest('details'); if (details) details.open = true;
  invalid.reportValidity(); return false;
}
function setBusy(value) { busy = value; $('#save').disabled = value || !loaded; $('#run-now').disabled = value || !loaded || !!currentState?.status.running; }
async function saveSettings() {
  if (!validateVisibleForm()) throw new Error('Проверь выделенные поля.');
  const next = await api('/api/config', readForm()); fillForm(next.config); renderStatus(next);
  dirty = false; $('#dirty-dot').hidden = true; $('#save-status').textContent = 'Настройки сохранены';
  return next;
}
form.noValidate = true;
form.addEventListener('input', markDirty);
form.addEventListener('change', markDirty);
form.addEventListener('submit', async event => {
  event.preventDefault(); if (busy || !loaded) return; setBusy(true);
  try { const result = await saveSettings(); notify(result.status.running ? 'Настройки сохранены. Текущий запуск завершится; изменения применятся к следующему.' : 'Настройки сохранены и применены.'); }
  catch (error) { notify(error.message, true); }
  finally { setBusy(false); }
});
$('#run-now').addEventListener('click', async () => {
  if (busy || !loaded) return; setBusy(true);
  try {
    if (dirty) await saveSettings();
    const state = await api('/api/state');
    if (state.status.running) notify('Запуск уже начался по расписанию.');
    else { await api('/api/run', {}); notify(state.config.dryrun ? 'Проверка запущена. История просмотров останется без изменений.' : 'Синхронизация запущена.'); }
    renderStatus(await api('/api/state'));
  } catch (error) { notify(error.message, true); }
  finally { setBusy(false); }
});
function addNew() { if (!loaded) return; addServer(); markDirty(); $$('.server-card').at(-1).scrollIntoView({block: 'center', behavior: 'smooth'}); }
$('#add-server').addEventListener('click', addNew); $('#add-first').addEventListener('click', addNew);
$('#refresh-logs').addEventListener('click', refreshLogs);
$$('.nav-item').forEach(button => button.addEventListener('click', () => switchTab(button.dataset.tab)));
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
makeDirections(); setBusy(false);
(async () => {
  try { const state = await api('/api/state'); fillForm(state.config); loaded = true; renderStatus(state); setBusy(false); }
  catch (error) { notify(error.message, true); }
})();
setInterval(async () => {
  if (!loaded || busy) return;
  try { renderStatus(await api('/api/state')); if (activeTab === 'logs') await refreshLogs(); }
  catch { $('#status-chip').textContent = 'Нет связи с приложением'; $('#status-chip').className = 'status-chip error'; }
}, 5000);
