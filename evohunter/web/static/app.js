// EvoHunter Workbench

const API = path => fetch(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({}),
}).then(r => r.json());

const API_PAYLOAD = (path, payload) => fetch(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
}).then(r => r.json());

let assessments = [];
let selectedIdx = -1;

// ═══════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════

async function init() {
  document.getElementById('run-btn').onclick = runPipeline;
  document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === 'Enter') runPipeline();
  });
  await checkApiKey();
  await updateStatusBar();
}

async function checkApiKey() {
  try {
    const cfg = await API('/api/config');
    const dot = document.getElementById('api-dot');
    const status = document.getElementById('api-status');
    if (cfg.has_api_key) {
      dot.classList.add('on');
      status.textContent = 'API ready';
    } else {
      status.textContent = 'no API key';
    }
  } catch {
    document.getElementById('api-status').textContent = 'API offline';
  }
}

async function updateStatusBar() {
  try {
    const data = await API_PAYLOAD('/api/evolution/data', { db_path: getDbPath() });
    const gens = data.generations || [];
    const last = gens.length ? gens[gens.length - 1] : null;
    document.getElementById('sb-generation').textContent = last ? `Gen ${last.generation}` : 'Gen 0';
    document.getElementById('sb-strategy').textContent = (data.current_strategy || {}).strategy || 'balanced';
    document.getElementById('gen-badge').textContent = last ? `Gen ${last.generation}` : 'Gen 0';
  } catch {}
}

function getDbPath() {
  try { return localStorage.getItem('evohunter_db_path') || '.evohunter/workbench.db'; }
  catch { return '.evohunter/workbench.db'; }
}

// ═══════════════════════════════════════════════════════════
// Pipeline
// ═══════════════════════════════════════════════════════════

async function runPipeline() {
  const jdText = document.getElementById('jd-input').value.trim();
  const resumeText = document.getElementById('resume-input').value.trim();
  if (!jdText || !resumeText) return;

  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.textContent = 'Running...';

  setPipelineNode('jd', 'running');
  clearResults();

  try {
    // Step 1: Parse JD
    let jobGene;
    try {
      const parsed = await API_PAYLOAD('/api/parse-job', { text: jdText });
      jobGene = parsed.job_gene || parsed;
      setPipelineNode('jd', 'completed');
    } catch (e) {
      setPipelineNode('jd', 'failed');
      throw e;
    }

    // Step 2: Assess candidates
    setPipelineNode('parse', 'running');
    try {
      const result = await API_PAYLOAD('/api/recruiter/assess', {
        job_gene: jobGene,
        resume_text: resumeText,
        language: 'zh',
      });
      assessments = [result];
      setPipelineNode('parse', 'completed');
    } catch (e) {
      setPipelineNode('parse', 'failed');
      assessments = [];
    }

    // Step 3+4: mark complete (outreach + report are per-candidate actions)
    setPipelineNode('outreach', 'completed');
    setPipelineNode('report', 'completed');

  } catch (e) {
    console.error('Pipeline error', e);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run Pipeline';
  }

  renderCards();
  document.getElementById('candidate-count').textContent = String(assessments.length);
  document.getElementById('sb-candidates').textContent = `${assessments.length} candidate${assessments.length !== 1 ? 's' : ''}`;
  updateAvgScore();
  updateStatusBar();
}

function setPipelineNode(nodeId, status) {
  const el = document.querySelector(`.pl-node[data-node="${nodeId}"]`);
  if (!el) return;
  el.classList.remove('completed', 'running', 'failed');
  if (status !== 'pending') el.classList.add(status);
}

function clearResults() {
  assessments = [];
  selectedIdx = -1;
  document.getElementById('cards-list').innerHTML = '';
  document.getElementById('detail-content').hidden = true;
  document.querySelector('.detail-empty').style.display = '';
  document.getElementById('candidate-count').textContent = '0';
  resetPipeline();
}

function resetPipeline() {
  document.querySelectorAll('.pl-node').forEach(el => {
    el.classList.remove('completed', 'running', 'failed');
  });
}

// ═══════════════════════════════════════════════════════════
// Cards
// ═══════════════════════════════════════════════════════════

function renderCards() {
  const list = document.getElementById('cards-list');
  if (!assessments.length) {
    list.innerHTML = `<div class="empty-hint"><div class="empty-icon">◈</div><p>No candidates assessed.<br>Check your JD and resume, then try again.</p></div>`;
    return;
  }

  list.innerHTML = assessments.map((a, i) => {
    const score = a.match_degree || 0;
    const scoreAttr = score >= 8 ? 'data-high' : score >= 6 ? 'data-mid' : 'data-low';
    const tags = (a.tech_tags || []).slice(0, 6);
    const conclusion = a.conclusion || '';
    const name = a.candidate_name || 'Unknown';

    return `
      <div class="candidate-card${i === selectedIdx ? ' selected' : ''}" data-idx="${i}" onclick="selectCard(${i})">
        <div class="card-name">${esc(name)}</div>
        <div class="card-score" ${scoreAttr}>${score}/10</div>
        <div class="card-tags">${tags.map(t => `<span class="card-tag">${esc(t)}</span>`).join('')}</div>
        <div class="card-conclusion">${esc(conclusion)}</div>
      </div>
    `;
  }).join('');
}

function selectCard(idx) {
  selectedIdx = idx;
  renderCards();
  renderDetail(idx);
}

// ═══════════════════════════════════════════════════════════
// Detail Panel
// ═══════════════════════════════════════════════════════════

function renderDetail(idx) {
  const a = assessments[idx];
  if (!a) return;

  document.querySelector('.detail-empty').style.display = 'none';
  const content = document.getElementById('detail-content');
  content.hidden = false;

  const score = a.match_degree || 0;
  const sc = score >= 8 ? 'var(--success)' : score >= 6 ? 'var(--warning)' : 'var(--error)';
  const tags = a.tech_tags || [];
  const reasons = a.reasons_for_recommendation || [];
  const points = a.main_match_points || [];
  const deductions = a.main_deductions || [];
  const recText = a.recommendation_text || '';
  const needsHuman = a.requires_human_input;

  content.innerHTML = `
    <div class="detail-name">${esc(a.candidate_name || 'Unknown')}</div>
    <div class="detail-score-row">
      <div class="detail-score-big" style="color:${sc}">${score}</div>
      <div class="detail-score-label">/ 10 · ${esc(a.conclusion || '')}</div>
    </div>

    ${points.length ? `
    <div class="detail-section">
      <h3>Match Points</h3>
      <ul class="detail-reasons">${points.map(p => `<li>${esc(p)}</li>`).join('')}</ul>
    </div>` : ''}

    ${deductions.length ? `
    <div class="detail-section">
      <h3>Deductions</h3>
      <ul class="detail-reasons">${deductions.map(d => `<li style="border-left-color:var(--error)">${esc(d)}</li>`).join('')}</ul>
    </div>` : ''}

    ${tags.length ? `
    <div class="detail-section">
      <h3>Tech Tags</h3>
      <div class="detail-tags">${tags.map(t => `<span class="detail-tag">${esc(t)}</span>`).join('')}</div>
    </div>` : ''}

    ${a.current_salary || a.current_level ? `
    <div class="detail-section">
      <h3>Compensation</h3>
      <p style="font-size:0.8125rem">${esc(a.current_salary || '—')} · ${esc(a.current_level || '—')}</p>
    </div>` : ''}

    ${a.reason_for_leaving ? `
    <div class="detail-section">
      <h3>Reason for Leaving</h3>
      <p style="font-size:0.8125rem">${esc(a.reason_for_leaving)}</p>
    </div>` : ''}

    ${needsHuman ? `
    <div class="detail-section">
      <p style="color:var(--warning);font-weight:600;font-size:0.875rem">Match below 7 — manual review needed</p>
      ${a.missing_fields && a.missing_fields.length ? `<p style="font-size:0.75rem;color:var(--muted)">Missing: ${a.missing_fields.join(', ')}</p>` : ''}
    </div>` : ''}

    ${recText ? `
    <div class="detail-section">
      <h3>Recommendation</h3>
      <div class="detail-rec-text">${esc(recText)}</div>
    </div>` : ''}

    <div class="detail-actions">
      ${!needsHuman ? `<button class="action-btn primary-action" onclick="draftOutreach(${idx})">Generate Outreach</button>` : ''}
      <button class="action-btn" onclick="generateReport(${idx})">Evaluation Report</button>
    </div>
  `;
}

// ═══════════════════════════════════════════════════════════
// Actions
// ═══════════════════════════════════════════════════════════

async function draftOutreach(idx) {
  const a = assessments[idx];
  if (!a) return;
  const jdText = document.getElementById('jd-input').value.trim();

  try {
    const jobGene = await parseJD(jdText);
    const res = await API_PAYLOAD('/api/draft-outreach', {
      job_gene: jobGene,
      candidate_gene: {
        candidate_id: a.candidate_name || 'c_001',
        skill_vector: a.tech_tags || [],
        years_of_experience: 0,
        salary_expectation: a.current_salary || 'unknown',
        location_preference: '',
        recent_projects: a.reasons_for_recommendation || [],
        availability: 'open',
        seniority_level: a.current_level || 'mid',
      },
      match_result: {
        candidate_id: a.candidate_name || 'c_001',
        job_id: 'j_001',
        match_score: (a.match_degree || 0) / 10,
        score_detail: {},
        recommendation_reason: a.conclusion || '',
      },
    });

    const panel = document.getElementById('detail-content');
    panel.insertAdjacentHTML('beforeend', `
      <div class="detail-section" style="margin-top:0.5rem">
        <h3>Outreach Draft</h3>
        <div class="detail-rec-text"><b>Subject:</b> ${esc(res.outreach_draft?.subject || '')}\n\n${esc(res.outreach_draft?.message_body || '')}</div>
      </div>
    `);
  } catch (e) {
    console.error('Outreach error', e);
  }
}

async function generateReport(idx) {
  const a = assessments[idx];
  if (!a) return;

  try {
    const res = await API_PAYLOAD('/api/evaluation/generate', {
      assessment: a,
      interview_qa: [],
      background_check: {},
      language: 'zh',
    });

    const rec = res.final_recommendation || '—';
    const panel = document.getElementById('detail-content');
    panel.insertAdjacentHTML('beforeend', `
      <div class="detail-section" style="margin-top:0.5rem">
        <h3>Evaluation Report</h3>
        <p style="font-size:0.875rem">Recommendation: <strong>${esc(rec)}</strong></p>
        <div class="detail-rec-text">${esc(res.resume_summary || '')}</div>
      </div>
    `);
  } catch (e) {
    console.error('Report error', e);
  }
}

async function parseJD(text) {
  try {
    const parsed = await API_PAYLOAD('/api/parse-job', { text });
    return parsed.job_gene || parsed;
  } catch {
    return { job_id: 'j_001', job_title: 'unknown', required_skills: [], preferred_skills: [], min_years_of_experience: 0, salary_range: 'unknown', location: 'unknown', seniority_level: 'unknown' };
  }
}

// ═══════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function updateAvgScore() {
  if (!assessments.length) {
    document.getElementById('sb-avg').textContent = 'avg —';
    return;
  }
  const avg = assessments.reduce((s, a) => s + (a.match_degree || 0), 0) / assessments.length;
  document.getElementById('sb-avg').textContent = `avg ${avg.toFixed(1)}`;
}

init();
