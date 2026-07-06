let phmData = null;

const formatNumber = (value) => new Intl.NumberFormat('en-US').format(value);
const riskClass = (risk) => risk.toLowerCase();

async function loadData() {
  const dataFiles = ['data/phm_dashboard_safe.json', 'data/sample_dashboard.json'];
  let lastError = null;
  for (const file of dataFiles) {
    try {
      const response = await fetch(file, { cache: 'no-store' });
      if (!response.ok) throw new Error(`${file}: ${response.status}`);
      phmData = await response.json();
      phmData.loadedFrom = file;
      renderAll();
      return;
    } catch (err) {
      lastError = err;
      console.warn('Could not load', file, err);
    }
  }
  throw lastError || new Error('No dashboard JSON found');
}

function renderAll() {
  const source = phmData.loadedFrom ? ` • ${phmData.loadedFrom}` : '';
  document.getElementById('lastUpdated').textContent = `Updated: ${phmData.lastUpdated}${source}`;
  renderKpis();
  renderRiskBars();
  renderWorkQueue();
  renderDiabetesRows(phmData.diabetesRegistry);
  renderCareGaps();
  renderSources();
}

function renderKpis() {
  const el = document.getElementById('kpiCards');
  el.innerHTML = phmData.kpis.map(kpi => `
    <article class="card">
      <div class="card-label">${kpi.label}</div>
      <div class="card-value">${formatNumber(kpi.value)}</div>
      <div class="card-note">${kpi.note}</div>
    </article>
  `).join('');
}

function renderRiskBars() {
  const total = phmData.riskDistribution.reduce((sum, x) => sum + x.count, 0);
  const el = document.getElementById('riskBars');
  el.innerHTML = phmData.riskDistribution.map(item => {
    const pct = total ? Math.round((item.count / total) * 100) : 0;
    return `
      <div class="bar-item">
        <div class="bar-head"><strong>${item.risk}</strong><span>${formatNumber(item.count)} (${pct}%)</span></div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      </div>
    `;
  }).join('');
}

function renderWorkQueue() {
  const el = document.getElementById('workQueue');
  el.innerHTML = phmData.workQueue.map(item => `
    <li><strong>${item.title}</strong> <span>${item.description}</span></li>
  `).join('');
}

function renderDiabetesRows(rows) {
  const el = document.getElementById('diabetesRows');
  el.innerHTML = rows.map(row => `
    <tr>
      <td><strong>${row.patientId}</strong><div class="small">${row.evidence}</div></td>
      <td>${row.age}</td>
      <td><span class="badge ${riskClass(row.risk)}">${row.risk}</span></td>
      <td>${row.hba1c ?? '—'}<div class="small">${row.hba1cDate ?? ''}</div></td>
      <td>${row.ldl ?? row.lipid ?? '—'}<div class="small">${row.lipidDate ?? ''}</div></td>
      <td>${row.egfr ?? '—'}</td>
      <td>${row.bp ?? '—'}</td>
      <td>${row.bmi ?? '—'}</td>
      <td>${row.gaps.join('<br>')}</td>
      <td>${row.action}</td>
    </tr>
  `).join('');
}

function renderCareGaps() {
  const el = document.getElementById('careGapCards');
  el.innerHTML = phmData.careGaps.map(gap => `
    <article class="gap-card">
      <h3>${gap.name}</h3>
      <div class="count">${formatNumber(gap.count)}</div>
      <p>${gap.rule}</p>
    </article>
  `).join('');
}

function renderSources() {
  const el = document.getElementById('sourceRows');
  el.innerHTML = phmData.sources.map(source => `
    <tr>
      <td><strong>${source.name}</strong></td>
      <td>${source.use}</td>
      <td><span class="badge safe">${source.status}</span></td>
    </tr>
  `).join('');
}

function setupNavigation() {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.section).classList.add('active');
    });
  });
}

function setupSearch() {
  document.getElementById('patientSearch').addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    const rows = phmData.diabetesRegistry.filter(row => {
      return [row.patientId, row.risk, row.evidence, row.action, ...row.gaps]
        .join(' ')
        .toLowerCase()
        .includes(q);
    });
    renderDiabetesRows(rows);
  });
}

setupNavigation();
setupSearch();
loadData().catch(err => {
  console.error(err);
  document.querySelector('.content').innerHTML = '<div class="panel"><h2>Data load failed</h2><p>Check that data/phm_dashboard_safe.json or data/sample_dashboard.json exists and that you are running through a local web server or GitHub Pages.</p></div>';
});
