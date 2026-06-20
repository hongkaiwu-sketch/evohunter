// EvoHunter Workbench — Search-driven marketplace

const API = (path, body) => fetch(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {}),
}).then(r => r.json());

const DB = () => getDbPath();

let pool = { jds: [], candidates: [] };
let selectedJds = new Set();
let selectedCandidates = new Set();
let matches = [];
let selectedMatch = -1;

// ═══════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════

async function init() {
  document.getElementById('search-btn').onclick = search;
  document.getElementById('search-skills').onkeydown = e => { if (e.key === 'Enter') search(); };
  document.getElementById('match-btn').onclick = matchSelected;
  document.getElementById('seed-btn').onclick = seedDemo;

  document.getElementById('add-jd-btn').onclick = () => toggleForm('jd', true);
  document.getElementById('add-resume-btn').onclick = () => toggleForm('resume', true);
  document.getElementById('jd-cancel-btn').onclick = () => toggleForm('jd', false);
  document.getElementById('resume-cancel-btn').onclick = () => toggleForm('resume', false);
  document.getElementById('jd-parse-btn').onclick = importJD;
  document.getElementById('resume-parse-btn').onclick = importResume;

  document.getElementById('jd-select-all').onclick = () => selectAll('jd', true);
  document.getElementById('jd-select-none').onclick = () => selectAll('jd', false);
  document.getElementById('candidate-select-all').onclick = () => selectAll('candidate', true);
  document.getElementById('candidate-select-none').onclick = () => selectAll('candidate', false);

  await checkApiKey();
  await search();
}

async function checkApiKey() {
  try {
    const cfg = await API('/api/config');
    document.getElementById('api-dot').classList.toggle('on', cfg.has_api_key);
    document.getElementById('api-status').textContent = cfg.has_api_key ? 'API ready' : 'no key';
  } catch { document.getElementById('api-status').textContent = 'offline'; }
}

function getDbPath() {
  try { return localStorage.getItem('evohunter_db_path') || '.evohunter/workbench.db'; }
  catch { return '.evohunter/workbench.db'; }
}

// ═══════════════════════════════════════════════════════════
// Search
// ═══════════════════════════════════════════════════════════

async function search() {
  const skills = document.getElementById('search-skills').value.trim();
  const location = document.getElementById('search-location').value.trim();
  const level = document.getElementById('search-level').value;

  try {
    const result = await API('/api/pool/search', {
      db_path: DB(),
      skills,
      location,
      seniority_level: level,
      side: 'both',
    });
    pool = result;
  } catch (e) {
    console.error('Search failed', e);
    pool = { jds: [], candidates: [] };
  }

  selectedJds.clear();
  selectedCandidates.clear();
  renderPool();
  updateCounts();
  updateStatusBar();
}

function renderPool() {
  renderJDs();
  renderCandidates();
}

function renderJDs() {
  const list = document.getElementById('jd-list');
  if (!pool.jds.length) {
    list.innerHTML = '<div class="empty-hint"><p>No JDs found. Try "Seed Demo" or adjust search.</p></div>';
    return;
  }
  list.innerHTML = pool.jds.map((jd, i) => {
    const id = jd.job_id || `jd_${i}`;
    const skills = [...(jd.required_skills || []), ...(jd.preferred_skills || [])].slice(0, 4).join(' · ');
    const checked = selectedJds.has(id) ? 'checked' : '';
    const sel = selectedJds.has(id) ? ' selected' : '';
    return `
      <div class="item-card${sel}" onclick="toggleJD('${id}')">
        <input type="checkbox" ${checked} onclick="event.stopPropagation();toggleJD('${id}')">
        <span class="item-icon">🏢</span>
        <div class="item-body">
          <div class="item-title">${esc(jd.job_title || 'Unknown')}</div>
          <div class="item-meta">${[jd.location, jd.salary_range, skills].filter(Boolean).join(' · ')}</div>
        </div>
      </div>
    `;
  }).join('');
  document.getElementById('jd-count').textContent = String(pool.jds.length);
}

function renderCandidates() {
  const list = document.getElementById('candidate-list');
  if (!pool.candidates.length) {
    list.innerHTML = '<div class="empty-hint"><p>No candidates found. Try "Seed Demo" or adjust search.</p></div>';
    return;
  }
  list.innerHTML = pool.candidates.map((c, i) => {
    const id = c.candidate_id || `c_${i}`;
    const skills = (c.skill_vector || []).slice(0, 4).join(' · ');
    const checked = selectedCandidates.has(id) ? 'checked' : '';
    const sel = selectedCandidates.has(id) ? ' selected' : '';
    return `
      <div class="item-card${sel}" onclick="toggleCandidate('${id}')">
        <input type="checkbox" ${checked} onclick="event.stopPropagation();toggleCandidate('${id}')">
        <span class="item-icon">👤</span>
        <div class="item-body">
          <div class="item-title">${esc(c.candidate_id || 'Unknown')}</div>
          <div class="item-meta">${[c.seniority_level, c.salary_expectation, skills].filter(Boolean).join(' · ')}</div>
        </div>
      </div>
    `;
  }).join('');
  document.getElementById('candidate-count').textContent = String(pool.candidates.length);
}

// ── Selection ────────────────────────────────────────────

function toggleJD(id) {
  if (selectedJds.has(id)) selectedJds.delete(id);
  else selectedJds.add(id);
  renderJDs();
  updateCounts();
}

function toggleCandidate(id) {
  if (selectedCandidates.has(id)) selectedCandidates.delete(id);
  else selectedCandidates.add(id);
  renderCandidates();
  updateCounts();
}

function selectAll(side, on) {
  if (side === 'jd') {
    selectedJds.clear();
    if (on) pool.jds.forEach(jd => selectedJds.add(jd.job_id));
    renderJDs();
  } else {
    selectedCandidates.clear();
    if (on) pool.candidates.forEach(c => selectedCandidates.add(c.candidate_id));
    renderCandidates();
  }
  updateCounts();
}

function updateCounts() {
  const jdN = selectedJds.size;
  const cN = selectedCandidates.size;
  document.getElementById('match-info').textContent =
    jdN && cN ? `${jdN} companies × ${cN} candidates = ${jdN * cN} matches`
    : 'Select companies and candidates to match';
  document.getElementById('match-btn').disabled = !(jdN && cN);
  document.getElementById('sb-jds').textContent = `${pool.jds.length} JDs`;
  document.getElementById('sb-candidates').textContent = `${pool.candidates.length} candidates`;
}

async function updateStatusBar() {
  try {
    const data = await API('/api/evolution/data', { db_path: DB() });
    const last = (data.generations || []).slice(-1)[0];
    document.getElementById('sb-generation').textContent = last ? `Gen ${last.generation}` : 'Gen 0';
    document.getElementById('gen-badge').textContent = last ? `Gen ${last.generation}` : 'Gen 0';
    document.getElementById('sb-strategy').textContent = (data.current_strategy || {}).strategy || 'balanced';
  } catch {}
}

// ═══════════════════════════════════════════════════════════
// Import
// ═══════════════════════════════════════════════════════════

function toggleForm(side, show) {
  document.getElementById(`${side}-form`).hidden = !show;
  if (show) document.getElementById(`${side}-input`).focus();
  else document.getElementById(`${side}-input`).value = '';
}

async function importJD() {
  const text = document.getElementById('jd-input').value.trim();
  if (!text) return;
  const msg = document.getElementById('jd-msg');
  msg.textContent = 'Parsing...';
  try {
    await API('/api/parse-job', { text, db_path: DB() });
    toggleForm('jd', false);
    msg.textContent = '';
    await search(); // refresh pool
  } catch (e) { msg.textContent = 'Failed: ' + e.message; }
}

async function importResume() {
  const text = document.getElementById('resume-input').value.trim();
  if (!text) return;
  const msg = document.getElementById('resume-msg');
  msg.textContent = 'Parsing...';
  try {
    await API('/api/parse-candidates', { text, db_path: DB() });
    toggleForm('resume', false);
    msg.textContent = '';
    await search();
  } catch (e) { msg.textContent = 'Failed: ' + e.message; }
}

// ═══════════════════════════════════════════════════════════
// Seed
// ═══════════════════════════════════════════════════════════

async function seedDemo() {
  const btn = document.getElementById('seed-btn');
  btn.textContent = 'Seeding...';
  btn.disabled = true;
  try {
    const result = await API('/api/pool/seed', { db_path: DB() });
    console.log('Seeded', result);
    await search();
  } catch (e) { console.error(e); }
  finally { btn.textContent = 'Seed Demo'; btn.disabled = false; }
}

// ═══════════════════════════════════════════════════════════
// Match
// ═══════════════════════════════════════════════════════════

async function matchSelected() {
  if (!selectedJds.size || !selectedCandidates.size) return;

  const btn = document.getElementById('match-btn');
  btn.disabled = true;
  btn.textContent = 'Matching...';
  matches = [];
  selectedMatch = -1;

  const jdList = pool.jds.filter(j => selectedJds.has(j.job_id));
  const cList = pool.candidates.filter(c => selectedCandidates.has(c.candidate_id));

  for (const jd of jdList) {
    for (const c of cList) {
      const resumeText = [
        c.candidate_id,
        (c.skill_vector || []).join(', '),
        `${c.years_of_experience} years`,
        c.seniority_level,
        c.salary_expectation,
        c.location_preference,
      ].filter(Boolean).join('. ');

      try {
        const result = await API('/api/recruiter/assess', {
          job_gene: jd,
          resume_text: resumeText,
          language: 'zh',
        });
        matches.push({ jdId: jd.job_id, jdTitle: jd.job_title, candidateId: c.candidate_id, assessment: result, score: result.match_degree || 0 });
      } catch (e) {
        matches.push({ jdId: jd.job_id, jdTitle: jd.job_title, candidateId: c.candidate_id, assessment: { error: e.message }, score: 0 });
      }
    }
  }

  matches.sort((a, b) => b.score - a.score);
  btn.disabled = false;
  btn.textContent = 'Match Selected';
  renderResults();
  updateStatusBar();
}

function renderResults() {
  document.getElementById('result-count').textContent = String(matches.length);
  const list = document.getElementById('results-list');

  if (!matches.length) {
    list.innerHTML = '<div class="empty-hint"><div class="empty-icon">◈</div><p>No matches yet.</p></div>';
    return;
  }

  list.innerHTML = matches.map((m, i) => {
    const s = m.score;
    const attr = s >= 8 ? 'data-high' : s >= 6 ? 'data-mid' : 'data-low';
    const a = m.assessment;
    const tags = (a.tech_tags || []).slice(0, 5);
    const badge = s >= 8 ? '<span class="result-badge strong">Strong</span>' : s >= 6 ? '<span class="result-badge hire">Hire</span>' : '<span class="result-badge review">Review</span>';

    return `
      <div class="result-card${i === selectedMatch ? ' selected' : ''}" onclick="selectMatch(${i})">
        <div class="result-pair">
          <span class="name">${esc(a.candidate_name || m.candidateId)}</span>
          <span class="arrow">→</span>
          <span class="jd-name">${esc(m.jdTitle)}</span>
        </div>
        <div class="result-tags">${tags.map(t => `<span class="result-tag">${esc(t)}</span>`).join('')}</div>
        <div class="result-score" ${attr}>${s}/10</div>
        ${badge}
      </div>
    `;
  }).join('');
}

function selectMatch(idx) {
  selectedMatch = idx;
  renderResults();
  showDetail(idx);
}

function showDetail(idx) {
  const m = matches[idx];
  if (!m) return;

  const wrap = document.getElementById('detail-wrap');
  const content = document.getElementById('detail-content');
  wrap.hidden = false;

  const a = m.assessment;
  const s = a.match_degree || 0;
  const sc = s >= 8 ? 'var(--success)' : s >= 6 ? 'var(--warning)' : 'var(--error)';
  const tags = a.tech_tags || [];
  const points = a.main_match_points || [];
  const deductions = a.main_deductions || [];
  const reasons = a.reasons_for_recommendation || [];
  const recText = a.recommendation_text || '';

  content.innerHTML = `
    <div class="detail-name">${esc(a.candidate_name || m.candidateId)} → ${esc(m.jdTitle)}</div>
    <div class="detail-score-row">
      <div class="detail-score-big" style="color:${sc}">${s}</div>
      <div class="detail-score-label">/ 10 · ${esc(a.conclusion || '')}</div>
    </div>
    <div class="detail-bidirectional">
      <div><div class="detail-bid-label">Hard Match</div><div class="detail-bid-score" style="color:${sc}">${(a.hard_match_score||0).toFixed(1)}/7</div></div>
      <div><div class="detail-bid-label">HR Bonus</div><div class="detail-bid-score" style="color:var(--accent)">${(a.hr_bonus_score||0).toFixed(1)}/3</div></div>
    </div>
    ${points.length ? `<div class="detail-section"><h3>Match Points</h3><ul class="detail-reasons">${points.map(p => `<li>${esc(p)}</li>`).join('')}</ul></div>` : ''}
    ${deductions.length ? `<div class="detail-section"><h3>Deductions</h3><ul class="detail-reasons">${deductions.map(d => `<li style="border-left-color:var(--error)">${esc(d)}</li>`).join('')}</ul></div>` : ''}
    ${reasons.length ? `<div class="detail-section"><h3>Recommendation Reasons</h3><ul class="detail-reasons">${reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ul></div>` : ''}
    ${tags.length ? `<div class="detail-section"><h3>Tech Tags</h3><div class="detail-tags">${tags.map(t => `<span class="detail-tag">${esc(t)}</span>`).join('')}</div></div>` : ''}
    ${a.current_salary||a.current_level ? `<div class="detail-section"><h3>Compensation</h3><p style="font-size:0.8125rem">${esc(a.current_salary||'—')} · ${esc(a.current_level||'—')}</p></div>` : ''}
    ${a.reason_for_leaving ? `<div class="detail-section"><h3>Reason for Leaving</h3><p style="font-size:0.8125rem">${esc(a.reason_for_leaving)}</p></div>` : ''}
    ${recText ? `<div class="detail-section"><h3>Recommendation</h3><div class="detail-rec-text">${esc(recText)}</div></div>` : ''}
    ${a.requires_human_input ? `<div class="detail-section"><p style="color:var(--warning);font-weight:600">⚠ Match below 7 — manual review needed</p>${a.missing_fields ? `<p style="font-size:0.75rem;color:var(--muted)">Missing: ${a.missing_fields.join(', ')}</p>` : ''}</div>` : ''}
    <div class="detail-actions">
      ${!a.requires_human_input ? `<button class="action-btn primary-action" onclick="draftOutreach(${idx})">Generate Outreach</button>` : ''}
      <button class="action-btn" onclick="generateReport(${idx})">Evaluation Report</button>
    </div>
  `;
  wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ═══════════════════════════════════════════════════════════
// Actions
// ═══════════════════════════════════════════════════════════

async function draftOutreach(idx) {
  const m = matches[idx]; if (!m) return;
  const jd = pool.jds.find(j => j.job_id === m.jdId); if (!jd) return;
  try {
    const res = await API('/api/draft-outreach', {
      job_gene: jd,
      candidate_gene: { candidate_id: m.candidateId, skill_vector: m.assessment.tech_tags||[], years_of_experience: 0, salary_expectation: m.assessment.current_salary||'', location_preference: '', recent_projects: [], availability: 'open', seniority_level: m.assessment.current_level||'mid' },
      match_result: { candidate_id: m.candidateId, job_id: jd.job_id, match_score: m.score/10, score_detail: {}, recommendation_reason: m.assessment.conclusion||'' },
    });
    document.getElementById('detail-content').insertAdjacentHTML('beforeend', `<div class="detail-section" style="margin-top:0.5rem"><h3>Outreach Draft</h3><div class="detail-rec-text"><b>Subject:</b> ${esc(res.outreach_draft?.subject||'')}\n\n${esc(res.outreach_draft?.message_body||'')}</div></div>`);
  } catch (e) { console.error(e); }
}

async function generateReport(idx) {
  const m = matches[idx]; if (!m) return;
  try {
    const res = await API('/api/evaluation/generate', { assessment: m.assessment, interview_qa: [], background_check: {} });
    document.getElementById('detail-content').insertAdjacentHTML('beforeend', `<div class="detail-section" style="margin-top:0.5rem"><h3>Evaluation Report</h3><p style="font-size:0.875rem">Recommendation: <strong>${esc(res.final_recommendation||'—')}</strong></p><div class="detail-rec-text">${esc(res.resume_summary||'')}</div></div>`);
  } catch (e) { console.error(e); }
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

init();
