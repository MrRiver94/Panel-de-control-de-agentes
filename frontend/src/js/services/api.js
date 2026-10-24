import { API_URL } from '../config.js';
import { State } from '../state.js';

const fetchApi = async (path, options = {}) => {
  const response = await fetch(API_URL + path, {
    ...options,
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
  return response.json();
};

export { fetchApi };
