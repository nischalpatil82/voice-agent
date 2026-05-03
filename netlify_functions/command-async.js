exports.handler = async function(event, context) {
  const BACKEND = process.env.VOICE_AGENT_BACKEND_URL || 'http://13.51.255.22';
  if (!BACKEND) {
    return { statusCode: 500, body: JSON.stringify({ error: 'VOICE_AGENT_BACKEND_URL not configured' }) };
  }

  try {
    const payload = event.body || '';
    const headers = { 'Content-Type': 'application/json' };
    // Forward session and request id headers if provided
    if (event.headers) {
      if (event.headers['x-session-id']) headers['X-Session-ID'] = event.headers['x-session-id'];
      if (event.headers['X-Session-ID']) headers['X-Session-ID'] = event.headers['X-Session-ID'];
      if (event.headers['x-request-id']) headers['X-Request-ID'] = event.headers['x-request-id'];
    }

    const res = await fetch(BACKEND.replace(/\/+$/,'') + '/command-async', {
      method: 'POST',
      headers,
      body: payload,
    });

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