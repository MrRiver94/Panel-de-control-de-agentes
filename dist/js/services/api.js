import { API_URL } from '../config.js';
import { State } from '../state.js';

const fetchApi = async (path, options = {}) => {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  else options.signal?.addEventListener('abort', cancel, { once: true });
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(API_URL + path, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-Operator-Id': State.operatorId,
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const text = await response.text();
      let detail;
      try {
        detail = JSON.parse(text).detail;
      } catch {}
      throw new Error(typeof detail === 'string' ? detail : `Error ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    if (error.name === 'AbortError' && !options.signal?.aborted)
      throw new Error(
        'La API no respondió a tiempo. El identificador de envío permite reintentar sin duplicar la misión.',
      );
    throw error;
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', cancel);
  }
};

export { fetchApi };
