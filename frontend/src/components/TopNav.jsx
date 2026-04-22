import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useDOTokens } from "../context/DOTokenContext";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import AddTokenDialog from "./AddTokenDialog";
import {
  CaretDown,
  Key,
  Plus,
  SignOut,
  Gear,
  User as UserIcon,
  Check,
} from "@phosphor-icons/react";

export default function TopNav() {
  const { user, logout } = useAuth();
  const { tokens, active, select } = useDOTokens();
  const [addOpen, setAddOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-50 bg-[#050505]/95 backdrop-blur-sm border-b border-white/10">
      <div className="flex items-center justify-between px-6 h-14 gap-4">
        <div className="flex items-center gap-6 min-w-0">
          <Link to="/droplets" className="flex items-center gap-2" data-testid="nav-home">
            <div className="w-7 h-7 bg-white text-black flex items-center justify-center font-black font-heading text-sm">
              DM
            </div>
            <span className="font-heading font-bold tracking-tight hidden sm:inline">
              Droplet Manager
            </span>
          </Link>
          <nav className="hidden md:flex items-center gap-5 text-sm">
            <NavLink to="/droplets">Droplets</NavLink>
            <NavLink to="/deploy">Deploy Wizard</NavLink>
            <NavLink to="/settings">Settings</NavLink>
          </nav>
        </div>

        <div className="flex items-center gap-3 min-w-0">
          {/* DO token switcher */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                data-testid="token-switcher"
                variant="outline"
                size="sm"
                className="rounded-none border-white/10 hover:bg-white/5 font-mono max-w-[240px]"
              >
                <Key size={14} className="mr-2 flex-shrink-0" />
                <span className="truncate">
                  {active ? active.name : "No token"}
                </span>
                <CaretDown size={12} className="ml-2 flex-shrink-0" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="bg-[#0f0f10] border-white/10 rounded-none min-w-[260px]"
            >
              <DropdownMenuLabel className="overline text-neutral-500">
                DO ACCOUNTS
              </DropdownMenuLabel>
              {tokens.length === 0 && (
                <div className="px-2 py-3 text-xs text-neutral-500">
                  No tokens yet. Add one below.
                </div>
              )}
              {tokens.map((t) => (
                <DropdownMenuItem
                  key={t.id}
                  onClick={() => select(t.id)}
                  data-testid={`select-token-${t.id}`}
                  className="cursor-pointer"
                >
                  <div className="flex items-start gap-2 w-full">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium flex items-center gap-1">
                        {t.name}
                        {active?.id === t.id && (
                          <Check size={12} className="text-accent-brand" />
                        )}
                      </div>
                      <div className="text-[10px] font-mono text-neutral-500 truncate">
                        {t.do_email || "—"}
                      </div>
                    </div>
                  </div>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuItem
                onClick={() => setAddOpen(true)}
                data-testid="add-token-menu"
                className="cursor-pointer"
              >
                <Plus size={14} className="mr-2" /> Add DO token
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* User menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                data-testid="user-menu"
                variant="outline"
                size="sm"
                className="rounded-none border-white/10 hover:bg-white/5"
              >
                {user?.picture ? (
                  <img
                    src={user.picture}
                    alt=""
                    className="w-5 h-5 rounded-full mr-2"
                  />
                ) : (
                  <UserIcon size={14} className="mr-2" />
                )}
                <span className="hidden sm:inline text-xs font-mono">
                  {user?.name || user?.email}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="bg-[#0f0f10] border-white/10 rounded-none min-w-[220px]"
            >
              <DropdownMenuLabel className="text-xs font-mono text-neutral-400">
                {user?.email}
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuItem
                onClick={() => navigate("/settings")}
                data-testid="menu-settings"
              >
                <Gear size={14} className="mr-2" /> Settings
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={async () => {
                  await logout();
                  navigate("/login");
                }}
                className="text-red-400 focus:text-red-400"
                data-testid="menu-logout"
              >
                <SignOut size={14} className="mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <AddTokenDialog open={addOpen} onOpenChange={setAddOpen} />
    </header>
  );
}

function NavLink({ to, children }) {
  return (
    <Link
      to={to}
      className="text-neutral-300 hover:text-white transition-colors"
      data-testid={`nav-${to.replace("/", "")}`}
    >
      {children}
    </Link>
  );
}
