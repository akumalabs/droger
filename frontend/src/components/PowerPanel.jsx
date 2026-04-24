import React, { useEffect, useState } from "react";
import { api, getActiveTokenId } from "../lib/api";
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
  Power,
  ArrowClockwise,
  StopCircle,
  Wrench,
  Lightning,
} from "@phosphor-icons/react";
import { toast } from "sonner";

const ACTIONS = [
  {
    key: "power_on",
    label: "Power On",
    icon: Power,
    desc: "Boot the droplet from a stopped state.",
    destructive: false,
    color: "#34D399",
  },
  {
    key: "reboot",
    label: "Reboot",
    icon: ArrowClockwise,
    desc: "Graceful restart of the droplet.",
    destructive: false,
    color: "#00E5FF",
  },
  {
    key: "reinstall_windows",
    label: "Reinstall Windows",
    icon: ArrowClockwise,
    desc: "Rebuild to Debian 13 and auto-install selected Windows version.",
    destructive: true,
    color: "#FBBF24",
  },
  {
    key: "shutdown",
    label: "Shutdown",
    icon: StopCircle,
    desc: "Graceful OS-level shutdown.",
    destructive: true,
    color: "#FBBF24",
  },
  {
    key: "power_off",
    label: "Power Off (hard)",
    icon: Power,
    desc: "Forcefully cut power. Unsaved data may be lost.",
    destructive: true,
    color: "#FB7185",
  },
  {
    key: "power_cycle",
    label: "Power Cycle",
    icon: Lightning,
    desc: "Hard power-off then power-on.",
    destructive: true,
    color: "#FB7185",
  },
  {
    key: "password_reset",
    label: "Reset Root Password",
    icon: Wrench,
    desc: "DO sends a new root password to account email.",
    destructive: true,
    color: "#FBBF24",
  },
];

function randomPw() {
  const chars =
    "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";
  let p = "";
  for (let i = 0; i < 12; i++) p += chars[Math.floor(Math.random() * chars.length)];
  return p + "!1";
}

export default function PowerPanel({ droplet, onChanged }) {
  const [pending, setPending] = useState(null);
  const [versions, setVersions] = useState([]);
  const [reinstallVersion, setReinstallVersion] = useState("win2022");
  const [reinstallPassword, setReinstallPassword] = useState(randomPw());
  const [reinstallPort, setReinstallPort] = useState(3389);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/do/windows-versions");
        const nextVersions = data.versions || [];
        setVersions(nextVersions);
        if (
          nextVersions.length > 0 &&
          !nextVersions.some((v) => v.key === reinstallVersion)
        ) {
          setReinstallVersion(nextVersions[0].key);
        }
      } catch {
      }
    })();
  }, []);

  const run = async (actionKey) => {
    try {
      if (actionKey === "reinstall_windows") {
        const tokenId = getActiveTokenId();
        if (!tokenId) {
          toast.error("No active token selected");
          return;
        }
        const port = Number(reinstallPort);
        if (!reinstallPassword || reinstallPassword.length < 6) {
          toast.error("RDP password must be at least 6 chars");
          return;
        }
        if (!port || port < 1 || port > 65535) {
          toast.error("RDP port must be between 1 and 65535");
          return;
        }
        await api.post(`/wizard/reinstall/${droplet.id}`, {
          token_id: tokenId,
          windows_version: reinstallVersion,
          rdp_password: reinstallPassword,
          rdp_port: port,
        });
      } else {
        await api.post(`/do/droplets/${droplet.id}/actions`, {
          action_type: actionKey,
        });
      }
      toast.success(`${actionKey} initiated`);
      setTimeout(onChanged, 1500);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Action failed");
    }
  };

  return (
    <div className="grid md:grid-cols-2 gap-0 border border-white/10">
      {ACTIONS.map((a) => {
        const Icon = a.icon;
        return (
          <div
            key={a.key}
            className="p-6 border-b border-r border-white/10 last:border-b-0 [&:nth-last-child(2)]:border-b-0 flex items-start gap-4"
            data-testid={`power-${a.key}`}
          >
            <div
              className="w-10 h-10 flex items-center justify-center border border-white/10 flex-shrink-0"
              style={{ color: a.color }}
            >
              <Icon size={20} weight="bold" />
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="font-heading font-bold mb-1">{a.label}</h4>
              <p className="text-xs text-neutral-400 mb-3">{a.desc}</p>
              <Button
                variant={a.destructive ? "outline" : "default"}
                size="sm"
                onClick={() => {
                  if (a.destructive) setPending(a);
                  else run(a.key);
                }}
                className={
                  a.destructive
                    ? "rounded-none border-white/15 hover:bg-white/5"
                    : "rounded-none bg-white text-black hover:bg-neutral-200"
                }
                data-testid={`power-run-${a.key}`}
              >
                Execute
              </Button>
            </div>
          </div>
        );
      })}

      <AlertDialog open={!!pending} onOpenChange={(o) => !o && setPending(null)}>
        <AlertDialogContent className="bg-[#0f0f10] border-white/10 rounded-none">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">
              Confirm: {pending?.label}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-neutral-400">
              {pending?.desc} Continue?
            </AlertDialogDescription>
          </AlertDialogHeader>

          {pending?.key === "reinstall_windows" && (
            <div className="space-y-3">
              <Field label="Windows Version">
                <Select value={reinstallVersion} onValueChange={setReinstallVersion}>
                  <SelectTrigger className="bg-black border-white/10 rounded-none">
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
              <div className="grid grid-cols-2 gap-3">
                <Field label="RDP Password">
                  <Input
                    type="text"
                    value={reinstallPassword}
                    onChange={(e) => setReinstallPassword(e.target.value)}
                    className="bg-black border-white/10 rounded-none font-mono"
                  />
                </Field>
                <Field label="RDP Port">
                  <Input
                    type="number"
                    min={1}
                    max={65535}
                    value={reinstallPort}
                    onChange={(e) => setReinstallPort(e.target.value)}
                    className="bg-black border-white/10 rounded-none font-mono"
                  />
                </Field>
              </div>
              <Button
                variant="outline"
                onClick={() => setReinstallPassword(randomPw())}
                className="rounded-none border-white/10"
              >
                Regenerate Password
              </Button>
            </div>
          )}

          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-none border-white/10">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pending) run(pending.key);
                setPending(null);
              }}
              className="rounded-none bg-red-600 hover:bg-red-500 text-white"
              data-testid="confirm-power-action"
            >
              Execute
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
