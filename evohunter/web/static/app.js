const state = {
  dbPath: ".evohunter/workbench.db",
  jobGene: null,
  candidateGenes: [],
  weightConfig: {},
  matchResults: [],
  outreachDraft: null
};

const localeState = {
  active: "en",
  fallback: {},
  messages: {}
};

const elements = {
  apiKeyDot: document.querySelector("#api-key-dot"),
  apiKeyStatus: document.querySelector("#api-key-status"),
  languageSelect: document.querySelector("#language-select"),
  jobText: document.querySelector("#job-text"),
  jobOutput: document.querySelector("#job-output"),
  jobMessage: document.querySelector("#job-message"),
  sourceInput: document.querySelector("#source-input"),
  candidateText: document.querySelector("#candidate-text"),
  candidateOutput: document.querySelector("#candidate-output"),
  candidateMessage: document.querySelector("#candidate-message"),
  weightsInput: document.querySelector("#weights-input"),
  scoreMessage: document.querySelector("#score-message"),
  resultsBody: document.querySelector("#results-body"),
  feedbackInput: document.querySelector("#feedback-input"),
  evolveOutput: document.querySelector("#evolve-output"),
  evolveMessage: document.querySelector("#evolve-message"),
  outreachOutput: document.querySelector("#outreach-output"),
  outreachMessage: document.querySelector("#outreach-message"),
  overviewCandidateCount: document.querySelector("#overview-candidate-count"),
  overviewHighestScore: document.querySelector("#overview-highest-score"),
  overviewGeneration: document.querySelector("#overview-generation"),
  overviewLastStep: document.querySelector("#overview-last-step"),
  parseJobButton: document.querySelector("#parse-job-button"),
  scrapeButton: document.querySelector("#scrape-button"),
  parseCandidatesButton: document.querySelector("#parse-candidates-button"),
  scoreButton: document.querySelector("#score-button"),
  evolveButton: document.querySelector("#evolve-button"),
  draftOutreachButton: document.querySelector("#draft-outreach-button"),
  stepItems: Object.fromEntries(
    Array.from(document.querySelectorAll("[data-step]")).map((step) => [step.dataset.step, step])
  )
};

const actionButtons = [
  elements.parseJobButton,
  elements.scrapeButton,
  elements.parseCandidatesButton,
  elements.scoreButton,
  elements.evolveButton,
  elements.draftOutreachButton
];

start();

async function start() {
  await initializeLocale();
  bindEvents();
  checkConfig();
  refreshOverview();
  syncControlState();
}

function bindEvents() {
  elements.languageSelect.addEventListener("change", () => setLocale(elements.languageSelect.value));
  elements.parseJobButton.addEventListener("click", parseJob);
  elements.scrapeButton.addEventListener("click", scrapeSource);
  elements.parseCandidatesButton.addEventListener("click", parseCandidates);
  elements.scoreButton.addEventListener("click", scoreCandidates);
  elements.evolveButton.addEventListener("click", evolveWeights);
  elements.draftOutreachButton.addEventListener("click", draftOutreach);
  for (const input of [
    elements.jobText,
    elements.sourceInput,
    elements.candidateText,
    elements.feedbackInput
  ]) {
    input.addEventListener("input", syncControlState);
  }
}

async function initializeLocale() {
  localeState.fallback = await loadLocale("en");
  const storedLocale = localStorage.getItem("evohunter_locale");
  const browserLocale = navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
  await setLocale(storedLocale || browserLocale);
}

async function loadLocale(locale) {
  const response = await fetch(`/static/locales/${locale}.json`);
  if (!response.ok) {
    throw new Error(`Locale ${locale} failed to load`);
  }
  return response.json();
}

async function setLocale(locale) {
  const activeLocale = locale === "zh" ? "zh" : "en";
  localeState.active = activeLocale;
  localeState.messages =
    activeLocale === "en" ? localeState.fallback : await loadLocale(activeLocale);
  localStorage.setItem("evohunter_locale", activeLocale);
  elements.languageSelect.value = activeLocale;
  applyLocale();
}

function applyLocale() {
  document.documentElement.lang = localeState.active === "zh" ? "zh-CN" : "en";
  for (const element of document.querySelectorAll("[data-i18n]")) {
    element.textContent = t(element.dataset.i18n);
  }
  for (const element of document.querySelectorAll("[data-i18n-placeholder]")) {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  }
  refreshButtonLabels();
  renderResults(state.matchResults);
}

function refreshButtonLabels() {
  for (const button of actionButtons) {
    if (!button) {
      continue;
    }
    button.dataset.label = t(button.dataset.i18n);
    if (button.dataset.busy !== "true") {
      button.textContent = button.dataset.label;
    }
  }
}

function t(key, values = {}) {
  const template = lookupMessage(localeState.messages, key) || lookupMessage(localeState.fallback, key) || key;
  return template.replace(/\{(\w+)\}/g, (match, name) =>
    Object.prototype.hasOwnProperty.call(values, name) ? values[name] : match
  );
}

function lookupMessage(payload, key) {
  return key.split(".").reduce((current, part) => {
    if (!current || typeof current !== "object") {
      return "";
    }
    return current[part];
  }, payload);
}

async function checkConfig() {
  try {
    const response = await apiPost("/api/config", {});
    elements.apiKeyDot.className = `status-dot ${response.has_api_key ? "ready" : "missing"}`;
    elements.apiKeyStatus.textContent = response.has_api_key
      ? t("messages.api_key_loaded")
      : t("messages.api_key_missing");
  } catch (error) {
    elements.apiKeyDot.className = "status-dot missing";
    elements.apiKeyStatus.textContent = t("messages.config_check_failed");
  }
}

async function scrapeSource() {
  setStepState("source", "active");
  await runTask(elements.candidateMessage, async () => {
    const sources = splitSources(elements.sourceInput.value);
    const payload = sources.length > 1 ? { sources } : { source: elements.sourceInput.value };
    const output = await apiPost("/api/scrape", payload);
    elements.candidateText.value = output.text;
    completeStep("source", "candidates");
    if (output.results) {
      const successCount = output.results.filter((result) => result.status === "success").length;
      return t("messages.sources_cleaned", { success: successCount, total: output.results.length });
    }
    return t("messages.source_cleaned");
  }, { button: elements.scrapeButton, busyLabel: t("messages.scraping") });
}

async function parseJob() {
  setStepState("job", "active");
  await runTask(elements.jobMessage, async () => {
    const output = await apiPost("/api/parse-job", { text: elements.jobText.value });
    state.jobGene = output.job_gene;
    renderJson(elements.jobOutput, state.jobGene);
    completeStep("job", "candidates");
    return t("messages.jd_parsed");
  }, { button: elements.parseJobButton, busyLabel: t("messages.parsing") });
}

async function parseCandidates() {
  setStepState("candidates", "active");
  await runTask(elements.candidateMessage, async () => {
    const output = await apiPost("/api/parse-candidates", { text: elements.candidateText.value });
    state.candidateGenes = output.candidate_genes;
    renderJson(elements.candidateOutput, state.candidateGenes);
    completeStep("candidates", "score");
    return t("messages.candidate_genes_parsed", { count: state.candidateGenes.length });
  }, { button: elements.parseCandidatesButton, busyLabel: t("messages.parsing") });
}

async function scoreCandidates() {
  setStepState("score", "active");
  await runTask(elements.scoreMessage, async () => {
    const jobGene = state.jobGene || parseJsonBlock(elements.jobOutput.textContent, "job gene");
    const candidateGenes = state.candidateGenes.length
      ? state.candidateGenes
      : parseJsonBlock(elements.candidateOutput.textContent, "candidate genes");
    const weightConfig = parseJsonBlock(elements.weightsInput.value, "weight config");
    const output = await apiPost("/api/score", {
      db_path: state.dbPath,
      job_gene: jobGene,
      candidate_genes: candidateGenes,
      weight_config: weightConfig
    });
    state.matchResults = output.match_results;
    state.jobGene = jobGene;
    state.candidateGenes = candidateGenes;
    renderResults(state.matchResults);
    completeStep("score", "evolve");
    await refreshOverview();
    return t("messages.results_scored", { count: state.matchResults.length });
  }, { button: elements.scoreButton, busyLabel: t("messages.scoring") });
}

async function evolveWeights() {
  setStepState("evolve", "active");
  await runTask(elements.evolveMessage, async () => {
    const weightConfig = parseJsonBlock(elements.weightsInput.value, "weight config");
    const feedbackEvents = parseJsonBlock(elements.feedbackInput.value, "feedback events");
    const output = await apiPost("/api/evolve", {
      db_path: state.dbPath,
      weight_config: weightConfig,
      feedback_events: feedbackEvents
    });
    state.weightConfig = output.weight_config;
    elements.weightsInput.value = JSON.stringify(state.weightConfig, null, 2);
    renderJson(elements.evolveOutput, state.weightConfig);
    completeStep("evolve");
    await refreshOverview();
    return t("messages.weights_evolved");
  }, { button: elements.evolveButton, busyLabel: t("messages.evolving") });
}

async function draftOutreach() {
  await runTask(elements.outreachMessage, async () => {
    const matchResult = state.matchResults[0];
    const candidateGene = state.candidateGenes.find(
      (candidate) => candidate.candidate_id === matchResult.candidate_id
    );
    const output = await apiPost("/api/draft-outreach", {
      job_gene: state.jobGene,
      candidate_gene: candidateGene,
      match_result: matchResult
    });
    state.outreachDraft = output.outreach_draft;
    renderJson(elements.outreachOutput, state.outreachDraft);
    return t("messages.outreach_generated");
  }, { button: elements.draftOutreachButton, busyLabel: t("messages.drafting") });
}

async function refreshOverview() {
  try {
    const overview = await apiPost("/api/overview", { db_path: state.dbPath });
    renderOverview(overview);
  } catch (error) {
    renderOverview({
      candidate_count: 0,
      highest_match_score: 0,
      current_generation: 0,
      last_step: "unavailable"
    });
  }
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Request failed");
  }
  return body;
}

async function runTask(messageElement, task, options = {}) {
  setButtonBusy(options.button, true, options.busyLabel);
  setMessage(messageElement, options.busyLabel || t("messages.working"), "");
  try {
    const successMessage = await task();
    setMessage(messageElement, successMessage, "success");
  } catch (error) {
    const activeStep = document.querySelector("[data-step].active");
    if (activeStep) {
      setStepState(activeStep.dataset.step, "error");
    }
    setMessage(messageElement, error.message, "error");
  } finally {
    setButtonBusy(options.button, false);
    syncControlState();
  }
}

function parseJsonBlock(value, label) {
  try {
    return JSON.parse(value || "{}");
  } catch (error) {
    throw new Error(t("errors.invalid_json", { label }));
  }
}

function renderJson(element, value) {
  element.textContent = JSON.stringify(value, null, 2);
}

function renderOverview(overview) {
  elements.overviewCandidateCount.textContent = String(overview.candidate_count || 0);
  elements.overviewHighestScore.textContent = Number(overview.highest_match_score || 0).toFixed(4);
  elements.overviewGeneration.textContent = String(overview.current_generation || 0);
  elements.overviewLastStep.textContent = overview.last_step || "none";
}

function renderResults(results) {
  if (!results.length) {
    elements.resultsBody.innerHTML = `<tr><td colspan="4">${t("messages.score_empty")}</td></tr>`;
    return;
  }
  elements.resultsBody.replaceChildren(
    ...results.map((result) => {
      const row = document.createElement("tr");
      row.append(
        tableCell(result.candidate_id),
        tableCell(result.match_score.toFixed(4)),
        detailCell(result.score_detail),
        tableCell(result.recommendation_reason)
      );
      return row;
    })
  );
}

function tableCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

function detailCell(scoreDetail) {
  const cell = document.createElement("td");
  const detail = document.createElement("div");
  detail.className = "score-detail";
  const entries = Object.entries(scoreDetail || {});
  entries.forEach(([key, value], index) => {
    const chip = document.createElement("span");
    chip.className = "score-chip";
    chip.textContent = `${key.replace("_score", "")}: ${Number(value).toFixed(2)}`;
    detail.append(chip);
    if (index < entries.length - 1) {
      detail.append(document.createTextNode(" "));
    }
  });
  cell.append(detail);
  return cell;
}

function setMessage(element, text, className) {
  element.textContent = text;
  element.className = `message ${className}`.trim();
}

function syncControlState() {
  setReadyDisabled(elements.parseJobButton, !elements.jobText.value.trim());
  setReadyDisabled(elements.scrapeButton, !elements.sourceInput.value.trim());
  setReadyDisabled(elements.parseCandidatesButton, !elements.candidateText.value.trim());
  setReadyDisabled(elements.scoreButton, !hasScorableData());
  setReadyDisabled(elements.evolveButton, !hasFeedbackEvents());
  setReadyDisabled(elements.draftOutreachButton, !hasOutreachData());
}

function hasScorableData() {
  const hasJob = Boolean(state.jobGene) || hasJsonObject(elements.jobOutput.textContent, "job_id");
  const hasCandidates =
    state.candidateGenes.length > 0 || hasNonEmptyJsonArray(elements.candidateOutput.textContent);
  return hasJob && hasCandidates;
}

function hasFeedbackEvents() {
  return hasNonEmptyJsonArray(elements.feedbackInput.value);
}

function hasOutreachData() {
  return Boolean(state.jobGene && state.candidateGenes.length && state.matchResults.length);
}

function splitSources(value) {
  return value
    .split(/\n+/)
    .map((source) => source.trim())
    .filter(Boolean);
}

function hasJsonObject(value, requiredKey) {
  try {
    const parsed = JSON.parse(value || "{}");
    return Boolean(parsed && typeof parsed === "object" && !Array.isArray(parsed) && parsed[requiredKey]);
  } catch (error) {
    return false;
  }
}

function hasNonEmptyJsonArray(value) {
  try {
    const parsed = JSON.parse(value || "[]");
    return Array.isArray(parsed) && parsed.length > 0;
  } catch (error) {
    return false;
  }
}

function setReadyDisabled(button, disabled) {
  if (button.dataset.busy === "true") {
    return;
  }
  button.disabled = disabled;
}

function setButtonBusy(button, busy, label = t("messages.working")) {
  if (!button) {
    return;
  }
  button.dataset.busy = busy ? "true" : "false";
  button.disabled = busy;
  button.textContent = busy ? label : button.dataset.label;
}

function completeStep(stepName, nextStepName) {
  setStepState(stepName, "completed");
  if (nextStepName) {
    setStepState(nextStepName, "active");
  }
}

function setStepState(stepName, status) {
  const step = elements.stepItems[stepName];
  if (!step) {
    return;
  }
  for (const item of Object.values(elements.stepItems)) {
    if (status === "active") {
      item.classList.remove("active");
      item.removeAttribute("aria-current");
    }
  }
  step.classList.remove("active", "completed", "error");
  if (status) {
    step.classList.add(status);
  }
  if (status === "active") {
    step.setAttribute("aria-current", "step");
  }
}
