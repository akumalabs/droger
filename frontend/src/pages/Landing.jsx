import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTokenCtx } from "../context/TokenContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { ArrowRight, Key, CircleNotch, Info } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function Landing() {
  const { connect, validating } = useTokenCtx();
  const [value, setValue] = useState("");
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!value.trim()) return;
    const res = await connect(value.trim());
    if (res.ok) {
      toast.success("Connected to DigitalOcean");
      navigate("/droplets");
    } else {
      toast.error(res.error || "Invalid token");
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div
        className="absolute inset-0 bg-cover bg-center opacity-30"
        style={{
          backgroundImage:
            "url(https://images.pexels.com/photos/29333569/pexels-photo-29333569.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940)",
        }}
      />
      <div className="absolute inset-0 bg-black/80 dotted-bg" />

      <div className="relative z-10 min-h-screen grid lg:grid-cols-2">
        {/* Left — brand */}
        <div className="flex flex-col justify-between p-10 lg:p-16 border-r border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white text-black flex items-center justify-center font-black font-heading">
              DM
            </div>
            <span className="overline">DROPLET // MANAGER</span>
          </div>

          <div className="max-w-xl">
            <p className="overline mb-6 text-accent-brand">CONTROL ROOM / v1.0</p>
            <h1 className="font-heading font-black text-5xl sm:text-6xl lg:text-7xl leading-[0.95] tracking-tight mb-8">
              Ship Windows<br />to any Droplet.
            </h1>
            <p className="text-neutral-300 text-base md:text-lg leading-relaxed max-w-lg">
              Connect your DigitalOcean account and operate droplets like a
              terminal — power, snapshots, rebuilds, and one-command{" "}
              <span className="text-accent-brand font-mono">Windows</span>{" "}
              installations via the AKUMA reinstall kernel.
            </p>

            <div className="mt-10 flex items-center gap-6 text-xs font-mono text-neutral-500">
              <span>FULL DROPLET CRUD</span>
              <span className="w-px h-3 bg-white/10" />
              <span>SNAPSHOTS</span>
              <span className="w-px h-3 bg-white/10" />
              <span>WIN 10/11/2012-2025</span>
            </div>
          </div>

          <div className="text-xs font-mono text-neutral-500">
            TOKEN IS KEPT IN SESSIONSTORAGE · NEVER PERSISTED SERVERSIDE
          </div>
        </div>

        {/* Right — token form */}
        <div className="flex items-center justify-center p-10 lg:p-16">
          <form
            onSubmit={onSubmit}
            className="w-full max-w-md border border-white/10 bg-[#0a0a0b] p-8"
            data-testid="token-form"
          >
            <div className="flex items-center gap-2 overline mb-2 text-accent-brand">
              <Key size={14} weight="bold" /> AUTHENTICATE
            </div>
            <h2 className="font-heading text-3xl font-bold mb-1">
              Enter your DO token
            </h2>
            <p className="text-sm text-neutral-400 mb-8">
              Create a{" "}
              <a
                className="text-accent-brand underline underline-offset-4"
                href="https://cloud.digitalocean.com/account/api/tokens"
                target="_blank"
                rel="noreferrer"
              >
                Personal Access Token
              </a>{" "}
              with read+write scope.
            </p>

            <label className="overline mb-2 block">API Token</label>
            <Input
              data-testid="token-input"
              type="password"
              autoComplete="off"
              placeholder="dop_v1_..."
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="bg-black border-white/10 focus:border-accent-brand focus:ring-0 font-mono rounded-none h-12"
            />

            <Button
              data-testid="connect-button"
              type="submit"
              disabled={validating || !value.trim()}
              className="w-full mt-6 h-12 rounded-none bg-white text-black hover:bg-neutral-200 font-semibold text-base"
            >
              {validating ? (
                <span className="flex items-center gap-2">
                  <CircleNotch className="animate-spin" size={18} /> Validating
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Connect <ArrowRight size={18} weight="bold" />
                </span>
              )}
            </Button>

            <div className="mt-6 flex items-start gap-2 text-xs text-neutral-500">
              <Info size={14} className="mt-0.5 flex-shrink-0" />
              <span>
                The token is stored only in your browser session. Closing the
                tab clears it.
              </span>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
