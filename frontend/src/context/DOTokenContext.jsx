import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getActiveTokenId, setActiveTokenId } from "../lib/api";
import { useAuth } from "./AuthContext";

const DOTokenContext = createContext(null);

export function DOTokenProvider({ children }) {
  const { user } = useAuth();
  const [tokens, setTokens] = useState([]);
  const [activeId, setActiveId] = useState(getActiveTokenId());
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) {
      setTokens([]);
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.get("/do-tokens");
      setTokens(data.tokens || []);
      // ensure active is valid
      const ids = (data.tokens || []).map((t) => t.id);
      const current = getActiveTokenId();
      if (current && !ids.includes(current)) {
        setActiveTokenId("");
        setActiveId("");
      }
      if (!current && ids.length > 0) {
        setActiveTokenId(ids[0]);
        setActiveId(ids[0]);
      }
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const select = (id) => {
    setActiveTokenId(id);
    setActiveId(id);
  };

  const addToken = async (name, token) => {
    const { data } = await api.post("/do-tokens", { name, token });
    await refresh();
    select(data.id);
    return data;
  };

  const renameToken = async (id, name) => {
    await api.patch(`/do-tokens/${id}`, { name });
    await refresh();
  };

  const deleteToken = async (id) => {
    await api.delete(`/do-tokens/${id}`);
    await refresh();
  };

  const active = tokens.find((t) => t.id === activeId) || null;

  return (
    <DOTokenContext.Provider
      value={{ tokens, active, activeId, loading, select, addToken, renameToken, deleteToken, refresh }}
    >
      {children}
    </DOTokenContext.Provider>
  );
}

export function useDOTokens() {
  return useContext(DOTokenContext);
}
