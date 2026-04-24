import axios from "axios"

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL as string | undefined
export const API = `${(BACKEND_URL || "http://localhost:8001").replace(/\/$/, "")}/api`

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
})

const ACTIVE_TOKEN_KEY = "active_do_token_id"

export function getActiveTokenId() {
  return localStorage.getItem(ACTIVE_TOKEN_KEY) || ""
}

export function setActiveTokenId(id: string) {
  if (id) localStorage.setItem(ACTIVE_TOKEN_KEY, id)
  else localStorage.removeItem(ACTIVE_TOKEN_KEY)
}

api.interceptors.request.use((cfg) => {
  const url = cfg.url || ""
  const needsToken = url.startsWith("/do/") && !url.startsWith("/do/windows-")
  if (needsToken) {
    const hasTokenParam = Boolean(cfg.params && typeof cfg.params === "object" && "token_id" in cfg.params)
    const tid = getActiveTokenId()
    if (tid && !hasTokenParam) {
      cfg.params = { ...(cfg.params || {}), token_id: tid }
    }
  }
  return cfg
})
