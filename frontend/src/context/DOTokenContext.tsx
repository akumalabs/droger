import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { api, getActiveTokenId, setActiveTokenId } from "../lib/api"
import { useAuth } from "./AuthContext"

type DOToken = {
  id: string
  name: string
  do_email?: string
  do_uuid?: string
  droplet_limit?: number
  created_at?: string
  last_used_at?: string
}

type DOTokenContextValue = {
  tokens: DOToken[]
  active: DOToken | null
  activeId: string
  loading: boolean
  select: (id: string) => void
  addToken: (name: string, token: string) => Promise<DOToken>
  renameToken: (id: string, name: string) => Promise<void>
  deleteToken: (id: string) => Promise<void>
  refresh: () => Promise<void>
}

const DOTokenContext = createContext<DOTokenContextValue | null>(null)

export function DOTokenProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const [tokens, setTokens] = useState<DOToken[]>([])
  const [activeId, setActiveId] = useState(getActiveTokenId())
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    if (!user) {
      setTokens([])
      return
    }
    setLoading(true)
    try {
      const { data } = await api.get<{ tokens: DOToken[] }>("/do-tokens")
      const next = data.tokens || []
      setTokens(next)
      const ids = next.map((t) => t.id)
      const current = getActiveTokenId()
      if (current && !ids.includes(current)) {
        setActiveTokenId("")
        setActiveId("")
      }
      if (!current && ids.length > 0) {
        setActiveTokenId(ids[0])
        setActiveId(ids[0])
      }
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const select = (id: string) => {
    setActiveTokenId(id)
    setActiveId(id)
  }

  const addToken = async (name: string, token: string) => {
    const { data } = await api.post<DOToken>("/do-tokens", { name, token })
    await refresh()
    select(data.id)
    return data
  }

  const renameToken = async (id: string, name: string) => {
    await api.patch(`/do-tokens/${id}`, { name })
    await refresh()
  }

  const deleteToken = async (id: string) => {
    await api.delete(`/do-tokens/${id}`)
    await refresh()
  }

  const active = tokens.find((t) => t.id === activeId) || null

  return (
    <DOTokenContext.Provider value={{ tokens, active, activeId, loading, select, addToken, renameToken, deleteToken, refresh }}>
      {children}
    </DOTokenContext.Provider>
  )
}

export function useDOTokens() {
  const ctx = useContext(DOTokenContext)
  if (!ctx) {
    throw new Error("useDOTokens must be used inside DOTokenProvider")
  }
  return ctx
}
