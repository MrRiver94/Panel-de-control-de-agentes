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
  if (!response.ok) throw new Error(await response.text());
  return response.json();
};

export { fetchApi };
