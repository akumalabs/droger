import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "../lib/api";

const TokenContext = createContext(null);

export function TokenProvider({ children }) {
  const [token, setTokenState] = useState(getToken());
  const [account, setAccount] = useState(null);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState("");

  const connect = useCallback(async (newToken) => {
    setValidating(true);
    setError("");
    try {
      setToken(newToken);
      setTokenState(newToken);
      const { data } = await api.get("/do/account");
      setAccount(data.account);
      return { ok: true };
    } catch (e) {
      setToken("");
      setTokenState("");
      setAccount(null);
      const msg = e?.response?.data?.detail || "Invalid token";
      setError(msg);
      return { ok: false, error: msg };
    } finally {
      setValidating(false);
    }
  }, []);

  const disconnect = useCallback(() => {
    setToken("");
    setTokenState("");
    setAccount(null);
  }, []);

  // auto-validate existing session token
  useEffect(() => {
    if (token && !account) {
      connect(token);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <TokenContext.Provider value={{ token, account, validating, error, connect, disconnect }}>
      {children}
    </TokenContext.Provider>
  );
}

export function useTokenCtx() {
  return useContext(TokenContext);
}
