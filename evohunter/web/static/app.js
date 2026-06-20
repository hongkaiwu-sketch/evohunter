// EvoHunter Workbench — Dual-sided marketplace

const API = (path, body) => fetch(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {}),
}).then(r => r.json());

let jds = [];
let candidates = [];
let matches = [];
let selectedMatch = -1;

// ═══════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════

async function init() {
  document.getElementById('add-jd-btn').onclick = () => showForm('jd');
  document.getElementById('add-resume-btn').onclick = () => showForm('resume');
  document.getElementById('jd-cancel-btn').onclick = () => hideForm('jd');
  document.getElementById('resume-cancel-btn').onclick = () => hideForm('resume');
  document.getElementById('jd-parse-btn').onclick = () => parseJD();
  document.getElementById('resume-parse-btn').onclick = () => parseResume();
  document.getElementById('match-all-btn').onclick = () => matchAll();

  await checkApiKey();
  await updateStatusBar();
  updateMatchBar();
}

async function checkApiKey() {
  try {
    const cfg = await API('/api/config');
    const dot = document.getElementById('api-dot');
    dot.classList.toggle('on', cfg.has_api_key);
    document.getElementById('api-status').textContent = cfg.has_api_key ? 'API ready' : 'no API key';
  } catch { document.getElementById('api-status').textContent = 'offline'; }
}

async function updateStatusBar() {
  try {
    const data = await API('/api/evolution/data', { db_path: getDbPath() });
    const gens = data.generations || [];
    const last = gens.length ? gens[gens.length - 1] : null;
    document.getElementById('sb-generation').textContent = last ? `Gen ${last.generation}` : 'Gen 0';
    document.getElementById('gen-badge').textContent = last ? `Gen ${last.generation}` : 'Gen 0';
    document.getElementById('sb-strategy').textContent = (data.current_strategy || {}).strategy || 'balanced';
  } catch {}
}

function getDbPath() {
  try { return localStorage.getItem('evohunter_db_path') || '.evohunter/workbench.db'; }
  catch { return '.evohunter/workbench.db'; }
}

// ═══════════════════════════════════════════════════════════
// JD Management
// ═══════════════════════════════════════════════════════════

function showForm(side) {
  document.getElementById(`${side}-form`).hidden = false;
  document.getElementById(`${side}-input`).focus();
}

function hideForm(side) {
  document.getElementById(`${side}-form`).hidden = true;
  document.getElementById(`${side}-input`).value = '';
  document.getElementById(`${side}-msg`).textContent = '';
}

async function parseJD() {
  const input = document.getElementById('jd-input');
  const text = input.value.trim();
  if (!text) return;

  const msg = document.getElementById('jd-msg');
  msg.textContent = 'Parsing...';
  try {
    const result = await API('/api/parse-job', { text });
    const jobGene = result.job_gene || result;
    jds.push({
      id: 'jd_' + Date.now(),
      text,
      jobGene,
      title: jobGene.job_title || extractTitle(text),
      skills: jobGene.required_skills || [],
      location: jobGene.location || '',
      salary: jobGene.salary_range || '',
    });
    hideForm('jd');
    renderJDs();
    updateCounts();
  } catch (e) {
    msg.textContent = 'Parse failed: ' + e.message;
  }
}

function extractTitle(text) {
  const firstLine = text.split('\n')[0].trim();
  return firstLine.slice(0, 60) || 'Untitled Role';
}

function removeJD(id) {
  jds = jds.filter(j => j.id !== id);
  matches = matches.filter(m => m.jdId !== id);
  renderJDs();
  renderResults();
  updateCounts();
}

function renderJDs() {
  const list = document.getElementById('jd-list');
  if (!jds.length) {
    list.innerHTML = '<div class="empty-hint-sm">No JDs yet. Click "+ Add JD" to start.</div>';
    return;
  }
  list.innerHTML = jds.map(j => `
    <div class="item-card">
      <span class="item-icon">🏢</span>
      <div class="item-body">
        <div class="item-title">${esc(j.title)}</div>
        <div class="item-meta">${[j.location, j.salary, (j.skills||[]).slice(0,3).join('·')].filter(Boolean).join(' · ') || 'No details'}</div>
      </div>
      <button class="item-remove" onclick="event.stopPropagation();removeJD('${j.id}')" title="Remove">×</button>
    </div>
  `).join('');
}

// ═══════════════════════════════════════════════════════════
// Candidate Management
// ═══════════════════════════════════════════════════════════

async function parseResume() {
  const input = document.getElementById('resume-input');
  const text = input.value.trim();
  if (!text) return;

  const msg = document.getElementById('resume-msg');
  msg.textContent = 'Parsing...';
  try {
    // Parse into structured candidate gene
    const parsed = await API('/api/parse-candidates', { text });
    const genes = parsed.candidate_genes || [];
    const gene = genes[0] || { candidate_id: 'c_' + Date.now(), skill_vector: [] };

    candidates.push({
      id: 'c_' + Date.now(),
      text,
      gene,
      name: gene.candidate_id || extractName(text),
      skills: gene.skill_vector || [],
      years: gene.years_of_experience || 0,
      level: gene.seniority_level || '',
      salary: gene.salary_expectation || '',
    });
    hideForm('resume');
    renderCandidates();
    updateCounts();
  } catch (e) {
    msg.textContent = 'Parse failed: ' + e.message;
  }
}

function extractName(text) {
  const firstLine = text.split('\n')[0].trim();
  return firstLine.slice(0, 30) || 'Unknown';
}

function removeCandidate(id) {
  candidates = candidates.filter(c => c.id !== id);
  matches = matches.filter(m => m.candidateId !== id);
  renderCandidates();
  renderResults();
  updateCounts();
}

function renderCandidates() {
  const list = document.getElementById('candidate-list');
  if (!candidates.length) {
    list.innerHTML = '<div class="empty-hint-sm">No candidates yet. Click "+ Add Resume" to start.</div>';
    return;
  }
  list.innerHTML = candidates.map(c => `
    <div class="item-card">
      <span class="item-icon">👤</span>
      <div class="item-body">
        <div class="item-title">${esc(c.name)}</div>
        <div class="item-meta">${[c.level, c.salary, (c.skills||[]).slice(0,3).join('·')].filter(Boolean).join(' · ') || 'No details'}</div>
      </div>
      <button class="item-remove" onclick="event.stopPropagation();removeCandidate('${c.id}')" title="Remove">×</button>
    </div>
  `).join('');
}

// ═══════════════════════════════════════════════════════════
// Cross Match
// ═══════════════════════════════════════════════════════════

async function matchAll() {
  if (!jds.length || !candidates.length) return;

  const btn = document.getElementById('match-all-btn');
  btn.disabled = true;
  btn.textContent = 'Matching...';
  matches = [];

  for (const jd of jds) {
    for (const candidate of candidates) {
      try {
        const result = await API('/api/recruiter/assess', {
          job_gene: jd.jobGene,
          resume_text: candidate.text,
          language: 'zh',
        });
        matches.push({
          jdId: jd.id,
          jdTitle: jd.title,
          candidateId: candidate.id,
          candidateName: result.candidate_name || candidate.name,
          score: result.match_degree || 0,
          assessment: result,
        });
      } catch (e) {
        matches.push({
          jdId: jd.id,
          jdTitle: jd.title,
          candidateId: candidate.id,
          candidateName: candidate.name,
          score: 0,
          assessment: { error: e.message },
        });
      }
    }
  }

  // Sort by bidirectional score descending
  matches.sort((a, b) => b.score - a.score);

  btn.disabled = false;
  btn.textContent = 'Match All';
  renderResults();
  updateStatusBar();
}

function renderResults() {
  const list = document.getElementById('results-list');
  const count = document.getElementById('result-count');
  count.textContent = String(matches.length);

  if (!matches.length) {
    list.innerHTML = '<div class="empty-hint"><div class="empty-icon">◈</div><p>No matches yet. Add JDs and resumes, then click "Match All".</p></div>';
    return;
  }

  list.innerHTML = matches.map((m, i) => {
    const score = m.score;
    const attr = score >= 8 ? 'data-high' : score >= 6 ? 'data-mid' : 'data-low';
    const tags = (m.assessment.tech_tags || []).slice(0, 5);
    const badge = score >= 8 ? '<span class="result-badge strong">Strong</span>'
                : score >= 6 ? '<span class="result-badge hire">Hire</span>'
                : '<span class="result-badge review">Review</span>';

    return `
      <div class="result-card${i === selectedMatch ? ' selected' : ''}" onclick="selectMatch(${i})">
        <div class="result-pair">
          <span class="name">${esc(m.candidateName)}</span>
          <span class="arrow">→</span>
          <span class="jd-name">${esc(m.jdTitle)}</span>
        </div>
        <div class="result-tags">${tags.map(t => `<span class="result-tag">${esc(t)}</span>`).join('')}</div>
        <div class="result-score" ${attr}>${score}/10</div>
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

  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');
  panel.hidden = false;

  const a = m.assessment;
  const score = a.match_degree || 0;
  const sc = score >= 8 ? 'var(--success)' : score >= 6 ? 'var(--warning)' : 'var(--error)';
  const tags = a.tech_tags || [];
  const points = a.main_match_points || [];
  const deductions = a.main_deductions || [];
  const recText = a.recommendation_text || '';
  const reasons = a.reasons_for_recommendation || [];

  content.innerHTML = `
    <div class="detail-name">${esc(a.candidate_name || m.candidateName)} → ${esc(m.jdTitle)}</div>
    <div class="detail-score-row">
      <div class="detail-score-big" style="color:${sc}">${score}</div>
      <div class="detail-score-label">/ 10 · ${esc(a.conclusion || '')}</div>
    </div>

    <div class="detail-bidirectional">
      <div>
        <div class="detail-bid-label">Company View</div>
        <div class="detail-bid-score" style="color:${sc}">${(a.hard_match_score || 0).toFixed(1)}/7</div>
        <div style="font-size:0.6875rem;color:var(--muted)">hard match</div>
      </div>
      <div>
        <div class="detail-bid-label">Candidate Fit</div>
        <div class="detail-bid-score" style="color:var(--accent)">${(a.hr_bonus_score || 0).toFixed(1)}/3</div>
        <div style="font-size:0.6875rem;color:var(--muted)">HR bonus</div>
      </div>
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

    ${reasons.length ? `
    <div class="detail-section">
      <h3>Recommendation Reasons</h3>
      <ul class="detail-reasons">${reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ul>
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

    ${recText ? `
    <div class="detail-section">
      <h3>Recommendation</h3>
      <div class="detail-rec-text">${esc(recText)}</div>
    </div>` : ''}

    ${a.requires_human_input ? `
    <div class="detail-section">
      <p style="color:var(--warning);font-weight:600;font-size:0.875rem">⚠ Match below 7 — manual review needed</p>
      ${a.missing_fields ? `<p style="font-size:0.75rem;color:var(--muted)">Missing: ${a.missing_fields.join(', ')}</p>` : ''}
    </div>` : ''}

    <div class="detail-actions">
      ${!a.requires_human_input ? `<button class="action-btn primary-action" onclick="draftOutreach(${idx})">Generate Outreach</button>` : ''}
      <button class="action-btn" onclick="generateReport(${idx})">Evaluation Report</button>
    </div>
  `;

  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ═══════════════════════════════════════════════════════════
// Actions
// ═══════════════════════════════════════════════════════════

async function draftOutreach(idx) {
  const m = matches[idx];
  if (!m) return;
  const jd = jds.find(j => j.id === m.jdId);
  if (!jd) return;

  try {
    const res = await API('/api/draft-outreach', {
      job_gene: jd.jobGene,
      candidate_gene: {
        candidate_id: m.candidateName,
        skill_vector: m.assessment.tech_tags || [],
        years_of_experience: 0,
        salary_expectation: m.assessment.current_salary || '',
        location_preference: '',
        recent_projects: [],
        availability: 'open',
        seniority_level: m.assessment.current_level || 'mid',
      },
      match_result: {
        candidate_id: m.candidateName,
        job_id: jd.jobGene?.job_id || 'j_001',
        match_score: m.score / 10,
        score_detail: {},
        recommendation_reason: m.assessment.conclusion || '',
      },
    });

    const panel = document.getElementById('detail-content');
    panel.insertAdjacentHTML('beforeend', `
      <div class="detail-section" style="margin-top:0.5rem">
        <h3>Outreach Draft</h3>
        <div class="detail-rec-text"><b>Subject:</b> ${esc(res.outreach_draft?.subject || '')}\n\n${esc(res.outreach_draft?.message_body || '')}</div>
      </div>
    `);
  } catch (e) { console.error(e); }
}

async function generateReport(idx) {
  const m = matches[idx];
  if (!m) return;

  try {
    const res = await API('/api/evaluation/generate', {
      assessment: m.assessment,
      interview_qa: [],
      background_check: {},
    });
    const panel = document.getElementById('detail-content');
    panel.insertAdjacentHTML('beforeend', `
      <div class="detail-section" style="margin-top:0.5rem">
        <h3>Evaluation Report</h3>
        <p style="font-size:0.875rem">Recommendation: <strong>${esc(res.final_recommendation || '—')}</strong></p>
        <div class="detail-rec-text">${esc(res.resume_summary || '')}</div>
      </div>
    `);
  } catch (e) { console.error(e); }
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

function updateCounts() {
  document.getElementById('match-jd-count').textContent = `${jds.length} JD${jds.length !== 1 ? 's' : ''}`;
  document.getElementById('match-candidate-count').textContent = `${candidates.length} candidate${candidates.length !== 1 ? 's' : ''}`;
  document.getElementById('match-total').textContent = `${jds.length * candidates.length} potential matches`;
  document.getElementById('sb-jds').textContent = `${jds.length} JD${jds.length !== 1 ? 's' : ''}`;
  document.getElementById('sb-candidates').textContent = `${candidates.length} candidate${candidates.length !== 1 ? 's' : ''}`;
  updateMatchBar();
}

function updateMatchBar() {
  const btn = document.getElementById('match-all-btn');
  btn.disabled = !(jds.length && candidates.length);
}

init();
