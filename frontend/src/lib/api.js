import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const TOKEN_KEY = "do_api_token";

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}
export function setToken(t) {
  if (t) sessionStorage.setItem(TOKEN_KEY, t);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export const api = axios.create({ baseURL: API });
api.interceptors.request.use((cfg) => {
  const t = getToken();
  if (t) cfg.headers["X-DO-Token"] = t;
  return cfg;
});
