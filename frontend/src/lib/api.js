import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

// attach active DO token id from localStorage automatically for /do/* and
// /wizard/* calls that need it
const ACTIVE_TOKEN_KEY = "active_do_token_id";
export function getActiveTokenId() {
  return localStorage.getItem(ACTIVE_TOKEN_KEY) || "";
}
export function setActiveTokenId(id) {
  if (id) localStorage.setItem(ACTIVE_TOKEN_KEY, id);
  else localStorage.removeItem(ACTIVE_TOKEN_KEY);
}

api.interceptors.request.use((cfg) => {
  const url = cfg.url || "";
  const needsToken = url.startsWith("/do/") && !url.startsWith("/do/windows-");
  if (needsToken) {
    const tid = getActiveTokenId();
    if (tid) {
      cfg.params = { ...(cfg.params || {}), token_id: tid };
    }
  }
  return cfg;
});
