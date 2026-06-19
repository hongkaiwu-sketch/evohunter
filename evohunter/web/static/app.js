const state = {
  jobGene: null,
  candidateGenes: [],
  weightConfig: {},
  matchResults: []
};

const elements = {
  apiKeyDot: document.querySelector("#api-key-dot"),
  apiKeyStatus: document.querySelector("#api-key-status"),
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
  parseJobButton: document.querySelector("#parse-job-button"),
  scrapeButton: document.querySelector("#scrape-button"),
  parseCandidatesButton: document.querySelector("#parse-candidates-button"),
  scoreButton: document.querySelector("#score-button"),
  evolveButton: document.querySelector("#evolve-button"),
  stepItems: Object.fromEntries(
    Array.from(document.querySelectorAll("[data-step]")).map((step) => [step.dataset.step, step])
  )
};

for (const button of [
  elements.parseJobButton,
  elements.scrapeButton,
  elements.parseCandidatesButton,
  elements.scoreButton,
  elements.evolveButton
]) {
  button.dataset.label = button.textContent;
}

elements.parseJobButton.addEventListener("click", parseJob);
elements.scrapeButton.addEventListener("click", scrapeSource);
elements.parseCandidatesButton.addEventListener("click", parseCandidates);
elements.scoreButton.addEventListener("click", scoreCandidates);
elements.evolveButton.addEventListener("click", evolveWeights);
for (const input of [
  elements.jobText,
  elements.sourceInput,
  elements.candidateText,
  elements.feedbackInput
]) {
  input.addEventListener("input", syncControlState);
}

checkConfig();
syncControlState();

async function checkConfig() {
  try {
    const response = await apiPost("/api/config", {});
    elements.apiKeyDot.className = `status-dot ${response.has_api_key ? "ready" : "missing"}`;
    elements.apiKeyStatus.textContent = response.has_api_key ? "Local API key loaded" : "Local API key missing";
  } catch (error) {
    elements.apiKeyDot.className = "status-dot missing";
    elements.apiKeyStatus.textContent = "Config check failed";
  }
}

async function scrapeSource() {
  setStepState("source", "active");
  await runTask(elements.candidateMessage, async () => {
    const output = await apiPost("/api/scrape", { source: elements.sourceInput.value });
    elements.candidateText.value = output.text;
    completeStep("source", "candidates");
    return "Source cleaned";
  }, { button: elements.scrapeButton, busyLabel: "Scraping" });
}

async function parseJob() {
  setStepState("job", "active");
  await runTask(elements.jobMessage, async () => {
    const output = await apiPost("/api/parse-job", { text: elements.jobText.value });
    state.jobGene = output.job_gene;
    renderJson(elements.jobOutput, state.jobGene);
    completeStep("job", "candidates");
    return "JD parsed";
  }, { button: elements.parseJobButton, busyLabel: "Parsing" });
}

async function parseCandidates() {
  setStepState("candidates", "active");
  await runTask(elements.candidateMessage, async () => {
    const output = await apiPost("/api/parse-candidates", { text: elements.candidateText.value });
    state.candidateGenes = output.candidate_genes;
    renderJson(elements.candidateOutput, state.candidateGenes);
    completeStep("candidates", "score");
    return `${state.candidateGenes.length} candidate gene${state.candidateGenes.length === 1 ? "" : "s"} parsed`;
  }, { button: elements.parseCandidatesButton, busyLabel: "Parsing" });
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
      job_gene: jobGene,
      candidate_genes: candidateGenes,
      weight_config: weightConfig
    });
    state.matchResults = output.match_results;
    renderResults(state.matchResults);
    completeStep("score", "evolve");
    return `${state.matchResults.length} result${state.matchResults.length === 1 ? "" : "s"} scored`;
  }, { button: elements.scoreButton, busyLabel: "Scoring" });
}

async function evolveWeights() {
  setStepState("evolve", "active");
  await runTask(elements.evolveMessage, async () => {
    const weightConfig = parseJsonBlock(elements.weightsInput.value, "weight config");
    const feedbackEvents = parseJsonBlock(elements.feedbackInput.value, "feedback events");
    const output = await apiPost("/api/evolve", {
      weight_config: weightConfig,
      feedback_events: feedbackEvents
    });
    state.weightConfig = output.weight_config;
    elements.weightsInput.value = JSON.stringify(state.weightConfig, null, 2);
    renderJson(elements.evolveOutput, state.weightConfig);
    completeStep("evolve");
    return "Weights evolved";
  }, { button: elements.evolveButton, busyLabel: "Evolving" });
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
  setMessage(messageElement, options.busyLabel || "Working", "");
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
    throw new Error(`Invalid ${label} JSON`);
  }
}

function renderJson(element, value) {
  element.textContent = JSON.stringify(value, null, 2);
}

function renderResults(results) {
  if (!results.length) {
    elements.resultsBody.innerHTML = '<tr><td colspan="4">Parse a JD and candidates to enable scoring.</td></tr>';
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

function setButtonBusy(button, busy, label = "Working") {
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
