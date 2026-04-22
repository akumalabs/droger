import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import TopNav from "../components/TopNav";
import { useDOTokens } from "../context/DOTokenContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
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
  AppWindow,
  Terminal,
  Copy,
  CircleNotch,
  CheckCircle,
  ArrowRight,
  Eye,
  EyeSlash,
} from "@phosphor-icons/react";
import StatusBadge from "../components/StatusBadge";

const STEPS = [
  { key: 1, label: "Linux Droplet" },
  { key: 2, label: "Windows Config" },
  { key: 3, label: "Deploy & Install" },
];

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
  const [name, setName] = useState("win-box-01");
  const [region, setRegion] = useState("");
  const [size, setSize] = useState("");
  const [image, setImage] = useState("ubuntu-22-04-x64");
  const [regions, setRegions] = useState([]);
  const [sizes, setSizes] = useState([]);
  const [images, setImages] = useState([]);
  const [sshKeys, setSshKeys] = useState([]);
  const [selectedKeys, setSelectedKeys] = useState([]);

  // Step 2
  const [versions, setVersions] = useState([]);
  const [winVersion, setWinVersion] = useState("win11pro");
  const [rdpPort, setRdpPort] = useState(3389);
  const [rdpPassword, setRdpPassword] = useState(randomPw());
  const [showPw, setShowPw] = useState(false);

  // Step 3
  const [deploying, setDeploying] = useState(false);
  const [result, setResult] = useState(null); // {droplet, command}
  const [droplet, setDroplet] = useState(null);
  const pollRef = useRef(null);

  const hasToken = !!active;

  // load options when token active
  useEffect(() => {
    if (!active) return;
    (async () => {
      try {
        const [r, s, i, k, v] = await Promise.all([
          api.get("/do/regions"),
          api.get("/do/sizes"),
          api.get("/do/images"),
          api.get("/do/ssh_keys"),
          api.get("/do/windows-versions"),
        ]);
        setRegions((r.data.regions || []).filter((x) => x.available));
        setSizes((s.data.sizes || []).filter((x) => x.available));
        setImages(r.data ? i.data.images || [] : []);
        setSshKeys(k.data.ssh_keys || []);
        setVersions(v.data.versions || []);
      } catch {
        toast.error("Failed to load options");
      }
    })();
  }, [active?.id]);

  // polling droplet status after deploy
  useEffect(() => {
    if (!result?.droplet?.id) return;
    const id = result.droplet.id;
    let stopped = false;
    const poll = async () => {
      try {
        const { data } = await api.get(`/do/droplets/${id}`);
        setDroplet(data.droplet);
        if (!stopped && data.droplet.status !== "active") {
          pollRef.current = setTimeout(poll, 5000);
        }
      } catch {
        pollRef.current = setTimeout(poll, 8000);
      }
    };
    poll();
    return () => {
      stopped = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [result?.droplet?.id]);

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
        image,
        ssh_keys: selectedKeys.length ? selectedKeys : null,
        windows_version: winVersion,
        rdp_password: rdpPassword,
        rdp_port: Number(rdpPort),
      });
      setResult(data);
      setDroplet(data.droplet);
      setStep(3);
      toast.success("Droplet creation started");
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
          Deploy Linux, install Windows
        </h1>
        <p className="text-sm text-neutral-400 mb-8">
          Using token{" "}
          <span className="font-mono text-accent-brand">{active.name}</span>
          {" · "}
          <span className="font-mono">{active.do_email}</span>
        </p>

        {/* stepper */}
        <div className="grid grid-cols-3 gap-0 border border-white/10 mb-8">
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
            <Row>
              <Field label="Droplet name">
                <Input
                  data-testid="w-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="bg-black border-white/10 rounded-none font-mono"
                />
              </Field>
              <Field label="Linux image (temporary — gets wiped)">
                <Select value={image} onValueChange={setImage}>
                  <SelectTrigger
                    data-testid="w-image"
                    className="bg-black border-white/10 rounded-none"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none max-h-60">
                    {images.map((img) => (
                      <SelectItem
                        key={img.slug || img.id}
                        value={img.slug || String(img.id)}
                      >
                        {img.distribution} {img.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </Row>

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
                onClick={() => setStep(2)}
                disabled={!name || !region || !size || !image}
                data-testid="w-next-1"
                className="rounded-none"
                style={{ background: "#00E5FF", color: "#000" }}
              >
                Next: Windows <ArrowRight size={14} weight="bold" className="ml-2" />
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5 border border-white/10 p-6">
            <div className="flex items-center gap-2 mb-2">
              <AppWindow size={20} className="text-accent-brand" weight="fill" />
              <h3 className="font-heading text-xl font-bold">
                Windows install configuration
              </h3>
            </div>

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

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                onClick={() => setStep(1)}
                className="rounded-none border-white/10"
                data-testid="w-back-2"
              >
                Back
              </Button>
              <Button
                onClick={deploy}
                disabled={deploying || rdpPassword.length < 6}
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

        {step === 3 && result && (
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
                  <CheckCircle size={14} weight="fill" /> Droplet is active. Run
                  the command below as root in the DigitalOcean console.
                </div>
              )}
            </div>

            <div className="border border-white/10 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <p className="overline">WINDOWS INSTALL COMMAND</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(result.command);
                    toast.success("Copied");
                  }}
                  className="rounded-none border-white/10"
                  data-testid="w-copy"
                >
                  <Copy size={14} className="mr-1" /> Copy
                </Button>
              </div>
              <pre
                data-testid="w-command"
                className="bg-black border border-white/10 p-4 text-xs font-mono text-green-400 whitespace-pre-wrap break-all max-h-72 overflow-auto"
              >
                {result.command}
              </pre>
              <ol className="text-sm text-neutral-300 list-decimal pl-5 space-y-1">
                <li>Wait until droplet status is <span className="text-green-400">active</span>.</li>
                <li>Open the DigitalOcean recovery console (button below).</li>
                <li>Paste the command as root. Wait ~15 minutes.</li>
                <li>
                  RDP to{" "}
                  <span className="font-mono text-accent-brand">
                    {publicIp || "<ip>"}:{rdpPort}
                  </span>{" "}
                  with user <span className="font-mono">Administrator</span>.
                </li>
              </ol>
              <div className="flex gap-2">
                <a
                  href={`https://cloud.digitalocean.com/droplets/${droplet?.id || result.droplet.id}/terminal/ui`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Button
                    data-testid="w-open-console"
                    className="rounded-none"
                    style={{ background: "#00E5FF", color: "#000" }}
                    disabled={!droplet || droplet.status !== "active"}
                  >
                    <Terminal size={14} weight="bold" className="mr-2" /> Open DO Console
                  </Button>
                </a>
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
