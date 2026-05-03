exports.handler = async function(event, context) {
  const BACKEND = process.env.VOICE_AGENT_BACKEND_URL || 'http://13.51.255.22';
  if (!BACKEND) {
    return { statusCode: 500, body: JSON.stringify({ error: 'VOICE_AGENT_BACKEND_URL not configured' }) };
  }

  // Try to obtain job id from path or query
  let jobId = null;
  if (event.path) {
    // path might be /command-result/<id>
    const m = event.path.match(/\/command-result\/(.+)$/);
    if (m) jobId = m[1];
  }
  if (!jobId && event.queryStringParameters && event.queryStringParameters.job_id) {
    jobId = event.queryStringParameters.job_id;
  }
  if (!jobId) {
    return { statusCode: 400, body: JSON.stringify({ error: 'missing job_id' }) };
  }

  try {
    const url = BACKEND.replace(/\/+$/,'') + '/command-result/' + encodeURIComponent(jobId);
    const res = await fetch(url, { method: 'GET' });
    const text = await res.text();
    return {
      statusCode: res.status,
      body: text,
      headers: { 'Content-Type': res.headers.get('content-type') || 'application/json' }
    };
  } catch (err) {
    return { statusCode: 502, body: JSON.stringify({ error: 'Upstream proxy error', detail: String(err) }) };
  }
};