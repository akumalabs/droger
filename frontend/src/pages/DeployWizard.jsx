import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import TopNav from "../components/TopNav";
import { useDOTokens } from "../context/DOTokenContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Progress } from "../components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";
import {
  Rocket,
  CircleNotch,
  CheckCircle,
  Eye,
  EyeSlash,
} from "@phosphor-icons/react";
import StatusBadge from "../components/StatusBadge";

const STEPS = [
  { key: 1, label: "Droplet Config" },
  { key: 2, label: "Deployment" },
];

const PROGRESS_LOG_MIN_WAIT = 30;
const PROGRESS_LOG_MAX_WAIT = 60;

function randomPw() {
  const chars =
    "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";
  let p = "";
  for (let i = 0; i < 12; i++) p += chars[Math.floor(Math.random() * chars.length)];
  return p + "!1";
}

export default function DeployWizard() {
  const { active } = useDOTokens();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);

  // Step 1
  const [name, setName] = useState("server-01");
  const [region, setRegion] = useState("");
  const [size, setSize] = useState("");
  const [regions, setRegions] = useState([]);
  const [sizes, setSizes] = useState([]);
  const [sshKeys, setSshKeys] = useState([]);
  const [selectedKeys, setSelectedKeys] = useState([]);

  // Step 2
  const [versions, setVersions] = useState([]);
  const [winVersion, setWinVersion] = useState("win10ltsc");
  const [rdpPort, setRdpPort] = useState(777);
  const [rdpPassword, setRdpPassword] = useState(randomPw());
  const [showPw, setShowPw] = useState(false);

  // Step 3
  const [deploying, setDeploying] = useState(false);
  const [result, setResult] = useState(null);
  const [droplet, setDroplet] = useState(null);
  const [progressReady, setProgressReady] = useState(false);
  const [progressLog, setProgressLog] = useState("");
  const [pingOk, setPingOk] = useState(false);
  const [rdpOpen, setRdpOpen] = useState(false);
  const [installComplete, setInstallComplete] = useState(false);
  const [installMessage, setInstallMessage] = useState("");
  const [progressWaitSeconds, setProgressWaitSeconds] = useState(0);
  const pollRef = useRef(null);

  const hasToken = !!active;

  // load options when token active
  useEffect(() => {
    if (!active) return;
    (async () => {
      try {
        const [r, s, k, v] = await Promise.all([
          api.get("/do/regions"),
          api.get("/do/sizes"),
          api.get("/do/ssh_keys"),
          api.get("/do/windows-versions"),
        ]);
        setRegions((r.data.regions || []).filter((x) => x.available));
        setSizes((s.data.sizes || []).filter((x) => x.available));
        setSshKeys(k.data.ssh_keys || []);
        setVersions(v.data.versions || []);
      } catch {
        toast.error("Failed to load options");
      }
    })();
  }, [active?.id]);

  // polling droplet + progress status after deploy
  useEffect(() => {
    if (!result?.droplet?.id || !active?.id) return;
    const id = result.droplet.id;
    let stopped = false;
    let elapsed = 0;
    const poll = async () => {
      try {
        const { data } = await api.get(`/wizard/progress/${id}`, {
          params: { token_id: active.id },
        });
        setDroplet(data.droplet || null);
        setProgressReady(Boolean(data.progress_ready));
        setProgressLog(data.log_tail || "");
        setPingOk(Boolean(data.ping_ok));
        setRdpOpen(Boolean(data.rdp_open));
        setInstallComplete(Boolean(data.install_complete));
        setInstallMessage(data.install_message || "");
      } catch {
      } finally {
        elapsed += 5;
        setProgressWaitSeconds(elapsed);
        if (!stopped) {
          pollRef.current = setTimeout(poll, 5000);
        }
      }
    };
    setProgressWaitSeconds(0);
    setPingOk(false);
    setRdpOpen(false);
    setInstallComplete(false);
    setInstallMessage("");
    poll();
    return () => {
      stopped = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [result?.droplet?.id, active?.id]);

  const availableSizes = useMemo(
    () => sizes.filter((s) => !region || s.regions.includes(region)),
    [sizes, region],
  );

  const toggleKey = (id) =>
    setSelectedKeys((prev) =>
      prev.includes(id) ? prev.filter((k) => k !== id) : [...prev, id],
    );

  const deploy = async () => {
    setDeploying(true);
    try {
      const { data } = await api.post("/wizard/deploy-windows", {
        token_id: active.id,
        name,
        region,
        size,
        ssh_keys: selectedKeys.length ? selectedKeys : null,
        windows_version: winVersion,
        rdp_password: rdpPassword,
        rdp_port: Number(rdpPort),
      });
      setResult(data);
      setDroplet(data.droplet);
      setStep(2);
      toast.success("Droplet creation started. Auto-install scheduled.");
    } catch (e) {
      toast.error(
        typeof e?.response?.data?.detail === "string"
          ? e.response.data.detail
          : "Deploy failed",
      );
    } finally {
      setDeploying(false);
    }
  };

  const publicIp =
    droplet?.networks?.v4?.find((n) => n.type === "public")?.ip_address;

  const progressEstimate = Math.min(
    100,
    Math.round((progressWaitSeconds / PROGRESS_LOG_MAX_WAIT) * 100),
  );
  const progressRemaining = Math.max(
    0,
    PROGRESS_LOG_MIN_WAIT - progressWaitSeconds,
  );

  if (!hasToken) {
    return (
      <div className="min-h-screen bg-[#050505]">
        <TopNav />
        <main className="px-6 py-20 max-w-xl mx-auto text-center">
          <h1 className="font-heading text-3xl font-bold mb-3">
            No DO token active
          </h1>
          <p className="text-neutral-400 mb-6">
            Add a DigitalOcean token first, then come back to deploy.
          </p>
          <Button
            onClick={() => navigate("/settings")}
            className="rounded-none bg-white text-black hover:bg-neutral-200"
          >
            Go to Settings
          </Button>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505]">
      <TopNav />
      <main className="px-6 py-8 max-w-4xl mx-auto">
        <p className="overline text-accent-brand mb-3">WIZARD // DEPLOY</p>
        <h1 className="font-heading text-4xl sm:text-5xl font-black tracking-tight mb-2">
          Auto Install Windows
        </h1>
        <p className="text-sm text-neutral-400 mb-8">
          Using token{" "}
          <span className="font-mono text-accent-brand">{active.name}</span>
          {" · "}
          <span className="font-mono">{active.do_email}</span>
        </p>

        {/* stepper */}
        <div className="grid grid-cols-2 gap-0 border border-white/10 mb-8">
          {STEPS.map((s) => (
            <div
              key={s.key}
              className={`p-4 border-r border-white/10 last:border-r-0 ${
                step === s.key
                  ? "bg-white/5"
                  : step > s.key
                    ? "bg-transparent"
                    : "bg-transparent"
              }`}
              data-testid={`step-${s.key}`}
            >
              <div className="overline mb-1">STEP {s.key}</div>
              <div
                className={`font-heading font-bold ${
                  step >= s.key ? "text-white" : "text-neutral-500"
                }`}
              >
                {s.label}
              </div>
            </div>
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-5 border border-white/10 p-6">
            <Field label="Droplet name">
              <Input
                data-testid="w-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="bg-black border-white/10 rounded-none font-mono"
              />
            </Field>

            <Row>
              <Field label="Region">
                <Select value={region} onValueChange={setRegion}>
                  <SelectTrigger
                    data-testid="w-region"
                    className="bg-black border-white/10 rounded-none"
                  >
                    <SelectValue placeholder="Pick a region" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none max-h-60">
                    {regions.map((r) => (
                      <SelectItem key={r.slug} value={r.slug}>
                        {r.name} ({r.slug})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Size">
                <Select value={size} onValueChange={setSize} disabled={!region}>
                  <SelectTrigger
                    data-testid="w-size"
                    className="bg-black border-white/10 rounded-none"
                  >
                    <SelectValue
                      placeholder={region ? "Pick a size" : "Pick region first"}
                    />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none max-h-60">
                    {availableSizes.map((s) => (
                      <SelectItem key={s.slug} value={s.slug}>
                        {s.slug} · {s.vcpus}vCPU/{s.memory}MB · ${s.price_monthly}/mo
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </Row>

            <Field label="Windows Version">
              <Select value={winVersion} onValueChange={setWinVersion}>
                <SelectTrigger
                  data-testid="w-win-version"
                  className="bg-black border-white/10 rounded-none"
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

            <Row>
              <Field label="RDP Password">
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Input
                      data-testid="w-rdp-pw"
                      type={showPw ? "text" : "password"}
                      value={rdpPassword}
                      onChange={(e) => setRdpPassword(e.target.value)}
                      className="bg-black border-white/10 rounded-none font-mono pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw((v) => !v)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-white"
                    >
                      {showPw ? <EyeSlash size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => setRdpPassword(randomPw())}
                    className="rounded-none border-white/10"
                  >
                    Regen
                  </Button>
                </div>
              </Field>
              <Field label="RDP Port">
                <Input
                  data-testid="w-rdp-port"
                  type="number"
                  min={1}
                  max={65535}
                  value={rdpPort}
                  onChange={(e) => setRdpPort(e.target.value)}
                  className="bg-black border-white/10 rounded-none font-mono"
                />
              </Field>
            </Row>

            {sshKeys.length > 0 && (
              <Field label={`SSH keys (optional — ${sshKeys.length})`}>
                <div className="border border-white/10 p-3 max-h-36 overflow-y-auto space-y-2">
                  {sshKeys.map((k) => (
                    <label
                      key={k.id}
                      className="flex items-center gap-2 text-sm cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedKeys.includes(k.id)}
                        onChange={() => toggleKey(k.id)}
                        className="accent-accent-brand"
                      />
                      <span className="font-mono text-xs">{k.name}</span>
                      <span className="text-neutral-500 text-xs truncate">
                        {k.fingerprint}
                      </span>
                    </label>
                  ))}
                </div>
              </Field>
            )}

            <div className="flex justify-end pt-2">
              <Button
                onClick={deploy}
                disabled={deploying || !name || !region || !size || rdpPassword.length < 6}
                data-testid="w-deploy"
                className="rounded-none bg-white text-black hover:bg-neutral-200"
              >
                {deploying ? (
                  <span className="flex items-center gap-2">
                    <CircleNotch className="animate-spin" size={14} /> Deploying
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Rocket size={14} weight="bold" /> Deploy droplet
                  </span>
                )}
              </Button>
            </div>
          </div>
        )}

        {step === 2 && result && (
          <div className="space-y-6">
            <div className="border border-white/10 p-6">
              <p className="overline mb-3">DROPLET STATUS</p>
              <div className="flex items-center gap-4 mb-4">
                <StatusBadge status={droplet?.status || "new"} />
                <div className="font-heading text-2xl font-bold">
                  {droplet?.name || result.droplet.name}
                </div>
                <span className="text-xs font-mono text-neutral-500">
                  #{droplet?.id || result.droplet.id}
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-0 border border-white/10">
                <Stat label="STATUS" value={droplet?.status || "new"} mono />
                <Stat
                  label="PUBLIC IP"
                  value={publicIp || "allocating…"}
                  mono
                  accent
                />
                <Stat
                  label="REGION"
                  value={(droplet?.region?.slug || result.droplet.region?.slug || "").toUpperCase()}
                  mono
                />
                <Stat label="SIZE" value={droplet?.size_slug || result.droplet.size_slug} mono />
              </div>

              {droplet?.status !== "active" && (
                <div className="mt-4 flex items-center gap-2 text-xs font-mono text-neutral-400">
                  <CircleNotch className="animate-spin" size={14} />
                  Waiting for droplet to become active… this usually takes 30-90
                  seconds.
                </div>
              )}
              {droplet?.status === "active" && (
                <div className="mt-4 flex items-center gap-2 text-xs font-mono text-green-400">
                  <CheckCircle size={14} weight="fill" /> Droplet is active. Auto-install should already be running.
                </div>
              )}
            </div>

            <div className="border border-white/10 p-6 space-y-4">

              {installComplete && (
                <div className="text-xs text-green-400 font-mono border border-green-500/30 p-3">
                  {installMessage || "Windows installation complete. You should be able to access it now."}
                </div>
              )}

              {!installComplete && (
                <div className="text-xs text-neutral-400 font-mono">
                  Connectivity checks · ICMP: {pingOk ? "OK" : "waiting"} · RDP {result?.rdp_port || rdpPort}: {rdpOpen ? "OPEN" : "waiting"}
                </div>
              )}

              <div className="space-y-3">
                <p className="overline">INSTALL LOG (LIVE)</p>
                {!progressReady && (
                  <div className="space-y-2">
                    <div className="text-xs text-neutral-400 font-mono">
                      Bootstrapping progress logs… usually visible in
                      {` ${PROGRESS_LOG_MIN_WAIT}-${PROGRESS_LOG_MAX_WAIT}s`}.
                      {progressRemaining > 0
                        ? ` ~${progressRemaining}s remaining before first logs.`
                        : " Checking every 5s for first output."}
                    </div>
                    <Progress
                      value={progressEstimate}
                      className="h-1.5 rounded-none bg-white/10 [&>div]:bg-accent-brand"
                    />
                  </div>
                )}
                {progressReady && (
                  <div className="text-xs text-green-400 font-mono">
                    Progress logs are live.
                  </div>
                )}
                <pre
                  className="bg-black border border-white/10 p-3 text-xs font-mono text-green-400 whitespace-pre-wrap break-all max-h-64 overflow-auto"
                  data-testid="wizard-progress-log"
                >
                  {progressLog || "No log output yet."}
                </pre>
              </div>

              <div className="flex gap-2">
                <Link to={`/droplets/${droplet?.id || result.droplet.id}`}>
                  <Button variant="outline" className="rounded-none border-white/10">
                    Open droplet detail
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function Row({ children }) {
  return <div className="grid sm:grid-cols-2 gap-4">{children}</div>;
}
function Field({ label, children }) {
  return (
    <div className="space-y-2">
      <Label className="overline">{label}</Label>
      {children}
    </div>
  );
}
function Stat({ label, value, mono, accent }) {
  return (
    <div className="p-4 border-r border-white/10 last:border-r-0">
      <div className="overline mb-1">{label}</div>
      <div
        className={`${mono ? "font-mono" : "font-heading font-bold"} ${
          accent ? "text-accent-brand" : "text-white"
        }`}
      >
        {value || "—"}
      </div>
    </div>
  );
}
