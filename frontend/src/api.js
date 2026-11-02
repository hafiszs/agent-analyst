/**
 * API client for Agent Analyst backend.
 * Supports healthchecks, multipart uploads, polling, and SSE streaming.
 */

const API_BASE = '/api';

export async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err) {
    return { docker: false, sandbox_image: false, llm_configured: false, error: err.message };
  }
}

export async function createJob(filesOrFile, query) {
  const formData = new FormData();
  if (Array.isArray(filesOrFile)) {
    filesOrFile.forEach((f) => {
      formData.append('files', f);
    });
  } else if (filesOrFile) {
    formData.append('files', filesOrFile);
  }
  formData.append('query', query);

  const res = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    let errMsg = `Gagal membuat job (Status ${res.status})`;
    try {
      const errData = await res.json();
      if (errData.detail) errMsg = errData.detail;
    } catch (_) {}
    throw new Error(errMsg);
  }

  return await res.json();
}

export async function getJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Gagal memuat job ${jobId}`);
  return await res.json();
}

export async function getEvidence(jobId, evidenceId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/evidence/${evidenceId}`);
  if (!res.ok) throw new Error(`Bukti ${evidenceId} tidak ditemukan`);
  return await res.json();
}

export async function sendFollowUpMessage(jobId, query, newFiles = [], history = []) {
  let res;
  if (newFiles && newFiles.length > 0) {
    const formData = new FormData();
    formData.append('query', query);
    if (history && history.length > 0) {
      formData.append('history', JSON.stringify(history));
    }
    newFiles.forEach((f) => {
      formData.append('files', f);
    });
    res = await fetch(`${API_BASE}/jobs/${jobId}/messages`, {
      method: 'POST',
      body: formData,
    });
  } else {
    res = await fetch(`${API_BASE}/jobs/${jobId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, history }),
    });
  }

  if (!res.ok) {
    let errMsg = `Gagal mengirim pesan lanjutan (Status ${res.status})`;
    try {
      const errData = await res.json();
      if (errData.detail) errMsg = errData.detail;
    } catch (_) {}
    throw new Error(errMsg);
  }
  return await res.json();
}

export function getFileUrl(jobId, filename) {
  return `${API_BASE}/jobs/${jobId}/files/${encodeURIComponent(filename)}`;
}

/**
 * Connect to the Server-Sent Events stream for a specific job.
 * Returns a cleanup function that closes the EventSource.
 */
export function subscribeJobEvents(jobId, onEvent, onError) {
  const url = `${API_BASE}/jobs/${jobId}/events`;
  const eventSource = new EventSource(url);

  // List of all events emitted by the backend
  const eventTypes = [
    'queued',
    'job_started',
    'step_started',
    'profile_ready',
    'plan_ready',
    'attempt_started',
    'code_generated',
    'sandbox_created',
    'sandbox_started',
    'stats',
    'stdout',
    'stderr',
    'limit_hit',
    'sandbox_destroyed',
    'attempt_succeeded',
    'diff_ready',
    'finding',
    'artifact',
    'report_ready',
    'warning',
    'step_finished',
    'job_done',
    'job_failed',
  ];

  let errorCount = 0;

  eventTypes.forEach((type) => {
    eventSource.addEventListener(type, (e) => {
      try {
        errorCount = 0;
        const data = JSON.parse(e.data);
        onEvent({ type, ...data });
        if (type === 'job_done' || type === 'job_failed') {
          eventSource.close();
        }
      } catch (err) {
        console.error('Error parsing SSE event data:', err);
      }
    });
  });

  eventSource.onerror = (err) => {
    errorCount += 1;
    console.warn('SSE connection notice:', err);
    // If the server permanently closed the connection or if retries fail 3 times consecutively, stop reconnecting.
    if (eventSource.readyState === EventSource.CLOSED || errorCount >= 3) {
      eventSource.close();
    }
    if (onError) onError(err);
  };

  return () => {
    eventSource.close();
  };
}
