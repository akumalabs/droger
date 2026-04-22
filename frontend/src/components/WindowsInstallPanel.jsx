import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./ui/alert-dialog";
import {
  AppWindow,
  Copy,
  Terminal,
  Warning,
  Eye,
  EyeSlash,
} from "@phosphor-icons/react";
import { toast } from "sonner";

function randomPw() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";
  const sym = "!@#$%";
  let p = "";
  for (let i = 0; i < 12; i++) p += chars[Math.floor(Math.random() * chars.length)];
  return p + sym[Math.floor(Math.random() * sym.length)] + "1";
}

export default function WindowsInstallPanel({ droplet }) {
  const [versions, setVersions] = useState([]);
  const [version, setVersion] = useState("win11pro");
  const [password, setPassword] = useState(randomPw());
  const [showPw, setShowPw] = useState(false);
  const [rdpPort, setRdpPort] = useState(3389);
  const [command, setCommand] = useState("");
  const [generating, setGenerating] = useState(false);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/do/windows-versions");
        setVersions(data.versions || []);
      } catch (e) {
        toast.error("Failed to load Windows versions");
      }
    })();
  }, []);

  const generate = async () => {
    if (!password || password.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }
    if (rdpPort < 1 || rdpPort > 65535) {
      toast.error("RDP port invalid");
      return;
    }
    setGenerating(true);
    try {
      const { data } = await api.post("/do/windows-script", {
        version,
        password,
        rdp_port: Number(rdpPort),
      });
      setCommand(data.command);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to generate");
    } finally {
      setGenerating(false);
    }
  };

  const copy = () => {
    navigator.clipboard.writeText(command);
    toast.success("Copied to clipboard");
  };

  const consoleUrl = `https://cloud.digitalocean.com/droplets/${droplet.id}/terminal/ui`;

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      {/* Config */}
      <div className="lg:col-span-2 border border-white/10 p-6 space-y-5">
        <div className="flex items-center gap-2 mb-4">
          <AppWindow size={22} className="text-accent-brand" weight="fill" />
          <h3 className="font-heading text-xl font-bold">Windows Reinstall</h3>
        </div>

        <div className="border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-300 flex gap-2">
          <Warning size={16} className="flex-shrink-0 mt-0.5" weight="fill" />
          <span>
            This wipes the droplet's disk. The droplet OS will be replaced with
            Windows. Back up data first.
          </span>
        </div>

        <Field label="Windows Version">
          <Select value={version} onValueChange={setVersion}>
            <SelectTrigger
              className="bg-black border-white/10 rounded-none"
              data-testid="win-version-select"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none">
              {versions.map((v) => (
                <SelectItem key={v.key} value={v.key}>
                  {v.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label="RDP Password">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="bg-black border-white/10 rounded-none font-mono pr-10"
                data-testid="win-password-input"
              />
              <button
                type="button"
                onClick={() => setShowPw((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-white"
                data-testid="toggle-pw"
              >
                {showPw ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <Button
              variant="outline"
              onClick={() => setPassword(randomPw())}
              className="rounded-none border-white/10"
              data-testid="regen-pw"
            >
              Regen
            </Button>
          </div>
        </Field>

        <Field label="RDP Port">
          <Input
            type="number"
            min={1}
            max={65535}
            value={rdpPort}
            onChange={(e) => setRdpPort(e.target.value)}
            className="bg-black border-white/10 rounded-none font-mono"
            data-testid="win-rdp-port-input"
          />
        </Field>

        <Button
          onClick={generate}
          disabled={generating}
          className="w-full rounded-none bg-white text-black hover:bg-neutral-200"
          data-testid="generate-command-button"
        >
          {generating ? "Generating…" : "Generate Install Command"}
        </Button>
      </div>

      {/* Command output + instructions */}
      <div className="lg:col-span-3 border border-white/10 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <p className="overline">GENERATED COMMAND</p>
          {command && (
            <Button
              variant="outline"
              size="sm"
              onClick={copy}
              className="rounded-none border-white/10"
              data-testid="copy-command"
            >
              <Copy size={14} className="mr-1" /> Copy
            </Button>
          )}
        </div>

        {command ? (
          <pre
            data-testid="generated-command"
            className="bg-black border border-white/10 p-4 text-xs font-mono text-green-400 whitespace-pre-wrap break-all max-h-72 overflow-auto"
          >
            {command}
          </pre>
        ) : (
          <div className="border border-dashed border-white/10 p-8 text-center text-sm text-neutral-500">
            Configure and click “Generate Install Command”.
          </div>
        )}

        <div className="border-t border-white/10 pt-4 space-y-3">
          <p className="overline">HOW TO RUN</p>
          <ol className="text-sm text-neutral-300 space-y-2 list-decimal pl-5">
            <li>Open the DigitalOcean Recovery Console for this droplet.</li>
            <li>Paste the command as <span className="font-mono text-accent-brand">root</span>.</li>
            <li>
              Wait ~10–15 minutes. The droplet reboots into Windows when done.
            </li>
            <li>
              Connect via RDP:{" "}
              <span className="font-mono text-accent-brand">
                {droplet.networks?.v4?.find((n) => n.type === "public")?.ip_address || "<ip>"}
                :{rdpPort}
              </span>{" "}
              user <span className="font-mono">Administrator</span> with the password above.
            </li>
          </ol>
          <div className="flex gap-2 pt-2">
            <a href={consoleUrl} target="_blank" rel="noreferrer">
              <Button
                disabled={!command}
                onClick={() => setConfirm(true)}
                className="rounded-none bg-accent-brand text-black hover:bg-cyan-300"
                style={{ background: "#00E5FF", color: "#000" }}
                data-testid="open-do-console"
              >
                <Terminal size={14} className="mr-2" weight="bold" /> Open DO Console
              </Button>
            </a>
          </div>
        </div>
      </div>

      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent className="bg-[#0f0f10] border-white/10 rounded-none">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">
              Confirm destructive install
            </AlertDialogTitle>
            <AlertDialogDescription className="text-neutral-400">
              Running this script will wipe the droplet and install Windows.
              Proceed only if you are ready.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-none border-white/10">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => setConfirm(false)}
              className="rounded-none bg-red-600 hover:bg-red-500"
            >
              I understand
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="space-y-2">
      <Label className="overline">{label}</Label>
      {children}
    </div>
  );
}
