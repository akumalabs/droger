import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTokenCtx } from "../context/TokenContext";
import { Button } from "./ui/button";
import { SignOut, Terminal } from "@phosphor-icons/react";

export default function TopNav() {
  const { account, disconnect } = useTokenCtx();
  const navigate = useNavigate();

  const onLogout = () => {
    disconnect();
    navigate("/");
  };

  return (
    <header className="sticky top-0 z-50 bg-[#050505]/95 backdrop-blur-sm border-b border-white/10">
      <div className="flex items-center justify-between px-6 h-14">
        <div className="flex items-center gap-8">
          <Link to="/droplets" className="flex items-center gap-2" data-testid="nav-home">
            <div className="w-7 h-7 bg-white text-black flex items-center justify-center font-black font-heading text-sm">
              DM
            </div>
            <span className="font-heading font-bold tracking-tight">Droplet Manager</span>
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-sm">
            <Link
              to="/droplets"
              className="text-neutral-300 hover:text-white transition-colors"
              data-testid="nav-droplets"
            >
              Droplets
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-4">
          {account && (
            <div className="hidden sm:flex items-center gap-3 text-xs font-mono text-neutral-400 border border-white/10 px-3 py-1.5">
              <Terminal size={14} />
              <span data-testid="account-email">{account.email}</span>
              <span className="w-px h-3 bg-white/10" />
              <span className="text-accent-brand" data-testid="account-limit">
                {account.droplet_limit} limit
              </span>
            </div>
          )}
          <Button
            data-testid="logout-button"
            variant="outline"
            size="sm"
            onClick={onLogout}
            className="rounded-none border-white/10 hover:bg-white/5"
          >
            <SignOut size={14} className="mr-2" /> Disconnect
          </Button>
        </div>
      </div>
    </header>
  );
}
