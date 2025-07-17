async function submitForm(e) {
  e.preventDefault();
  const form = e.target;
  const data = new FormData(form);
  const res = await fetch('/jobs/upload', { method: 'POST', body: data });
  const resp = await res.json();
  document.getElementById('status').textContent = 'queued';
  pollStatus(resp.job_id);
}

document.getElementById('upload-form').addEventListener('submit', submitForm);

async function pollStatus(id) {
  const statusEl = document.getElementById('status');
  const resultsEl = document.getElementById('results');
  while (true) {
    const r = await fetch(`/jobs/${id}`);
    if (!r.ok) break;
    const data = await r.json();
    statusEl.textContent = data.status;
    if (data.status === 'finished') {
      resultsEl.innerHTML = `<a href="/jobs/${id}/results">View Results</a>`;
      break;
    } else if (data.status === 'failed') {
      resultsEl.textContent = 'failed';
      break;
    }
    await new Promise(r => setTimeout(r, 2000));
  }
}
