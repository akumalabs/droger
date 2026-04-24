import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, getActiveTokenId } from "../lib/api";
import TopNav from "../components/TopNav";
import StatusBadge from "../components/StatusBadge";
import SnapshotsPanel from "../components/SnapshotsPanel";
import PowerPanel from "../components/PowerPanel";
import { Button } from "../components/ui/button";
import { Progress } from "../components/ui/progress";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { ArrowLeft, ArrowsClockwise, CheckCircle, CircleNotch } from "@phosphor-icons/react";
import { toast } from "sonner";

const PROGRESS_LOG_MIN_WAIT = 30;
const PROGRESS_LOG_MAX_WAIT = 60;

export default function DropletDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [droplet, setDroplet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reinstallState, setReinstallState] = useState(null);
  const [progressReady, setProgressReady] = useState(false);
  const [progressLog, setProgressLog] = useState("");
  const [pingOk, setPingOk] = useState(false);
  const [rdpOpen, setRdpOpen] = useState(false);
  const [installComplete, setInstallComplete] = useState(false);
  const [installMessage, setInstallMessage] = useState("");
  const [progressWaitSeconds, setProgressWaitSeconds] = useState(0);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/do/droplets/${id}`);
      setDroplet(data.droplet);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load droplet");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!id) return;
    const tokenId = getActiveTokenId();
    if (!tokenId) return;
    (async () => {
      try {
        const { data } = await api.get(`/wizard/progress/${id}`, {
          params: { token_id: tokenId },
        });
        if (data?.windows_version && data?.rdp_port) {
          setReinstallState({
            windowsVersion: data.windows_version,
            rdpPassword: data.rdp_password,
            rdpPort: data.rdp_port,
          });
          setProgressReady(Boolean(data.progress_ready));
          setProgressLog(data.log_tail || "");
          setPingOk(Boolean(data.ping_ok));
          setRdpOpen(Boolean(data.rdp_open));
          setInstallComplete(Boolean(data.install_complete));
          setInstallMessage(data.install_message || "");
        }
      } catch {
      }
    })();
  }, [id]);

  useEffect(() => {
    if (!reinstallState || !id) return;
    const tokenId = getActiveTokenId();
    if (!tokenId) return;
    let stopped = false;
    let elapsed = 0;
    const poll = async () => {
      try {
        const { data } = await api.get(`/wizard/progress/${id}`, {
          params: { token_id: tokenId },
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
    setProgressReady(false);
    setProgressLog("");
    setPingOk(false);
    setRdpOpen(false);
    setInstallComplete(false);
    setInstallMessage("");
    setProgressWaitSeconds(0);
    poll();
    return () => {
      stopped = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [reinstallState, id]);

  if (loading && !droplet) {
    return (
      <div className="min-h-screen bg-[#050505]">
        <TopNav />
        <div className="p-10 text-neutral-500 font-mono">Loading droplet…</div>
      </div>
    );
  }
  if (!droplet) {
    return (
      <div className="min-h-screen bg-[#050505]">
        <TopNav />
        <div className="p-10">
          <Link to="/droplets" className="text-accent-brand hover:underline">
            ← Back to droplets
          </Link>
        </div>
      </div>
    );
  }

  const publicIp =
    droplet.networks?.v4?.find((n) => n.type === "public")?.ip_address || "—";
  const privateIp =
    droplet.networks?.v4?.find((n) => n.type === "private")?.ip_address || "—";

  const progressEstimate = Math.min(
    100,
    Math.round((progressWaitSeconds / PROGRESS_LOG_MAX_WAIT) * 100),
  );
  const progressRemaining = Math.max(
    0,
    PROGRESS_LOG_MIN_WAIT - progressWaitSeconds,
  );

  return (
    <div className="min-h-screen bg-[#050505]">
      <TopNav />

      <main className="px-6 py-8 max-w-[1400px] mx-auto">
        <button
          onClick={() => navigate("/droplets")}
          className="text-xs font-mono text-neutral-400 hover:text-accent-brand flex items-center gap-1 mb-6"
          data-testid="back-link"
        >
          <ArrowLeft size={14} /> FLEET / DROPLETS
        </button>

        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-10">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <StatusBadge status={droplet.status} />
              <span className="text-xs font-mono text-neutral-500">
                #{droplet.id}
              </span>
            </div>
            <h1 className="font-heading text-4xl sm:text-5xl font-black tracking-tight">
              {droplet.name}
            </h1>
            <p className="text-sm text-neutral-400 mt-2 font-mono">
              {droplet.region?.name} · {droplet.size_slug} ·{" "}
              <span className="text-accent-brand">{publicIp}</span>
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={load}
              className="rounded-none border-white/10 hover:bg-white/5"
              data-testid="refresh-detail"
            >
              <ArrowsClockwise size={16} className="mr-2" /> Refresh
            </Button>
          </div>
        </div>

        {reinstallState && (
          <div className="border border-white/10 p-6 mb-10 space-y-4">
            <p className="overline">REINSTALL STATUS</p>
            <div className="text-sm text-neutral-300 space-y-1">
              <div>
                Target Windows: <span className="font-mono text-accent-brand">{reinstallState.windowsVersion}</span>
              </div>
              <div>
                RDP: <span className="font-mono text-accent-brand">{publicIp}:{reinstallState.rdpPort}</span> (Administrator)
              </div>
              <div>
                Password: <span className="font-mono text-accent-brand">{reinstallState.rdpPassword || "Unavailable"}</span>
              </div>
              <div>
                Progress page: <span className="font-mono text-accent-brand">http://{publicIp}/</span>
              </div>
            </div>

            {installComplete && (
              <div className="text-xs text-green-400 font-mono border border-green-500/30 p-3">
                {installMessage || "Windows installation complete. You should be able to access it now."}
              </div>
            )}
            {!installComplete && (
              <div className="text-xs text-neutral-400 font-mono">
                Connectivity checks · ICMP: {pingOk ? "OK" : "waiting"} · RDP {reinstallState.rdpPort}: {rdpOpen ? "OPEN" : "waiting"}
              </div>
            )}

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
              <div className="text-xs text-green-400 font-mono flex items-center gap-2">
                <CheckCircle size={14} weight="fill" /> Progress logs are live.
              </div>
            )}

            <pre
              className="bg-black border border-white/10 p-3 text-xs font-mono text-green-400 whitespace-pre-wrap break-all max-h-64 overflow-auto"
              data-testid="reinstall-progress-log"
            >
              {progressLog || "No log output yet."}
            </pre>

            {droplet.status !== "active" && (
              <div className="text-xs text-neutral-400 font-mono flex items-center gap-2">
                <CircleNotch className="animate-spin" size={14} /> Waiting for droplet to become active.
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-0 border border-white/10 mb-10">
          <Spec label="VCPUS" value={droplet.vcpus} />
          <Spec label="MEMORY" value={`${droplet.memory} MB`} />
          <Spec label="DISK" value={`${droplet.disk} GB`} />
          <Spec label="IMAGE" value={`${droplet.image?.distribution || ""}`} mono />
          <Spec label="PUBLIC IPV4" value={publicIp} mono accent />
          <Spec label="PRIVATE IPV4" value={privateIp} mono />
          <Spec label="REGION" value={droplet.region?.slug?.toUpperCase()} mono />
          <Spec
            label="CREATED"
            value={new Date(droplet.created_at).toLocaleDateString()}
            mono
          />
        </div>

        <Tabs defaultValue="power" className="w-full">
          <TabsList className="bg-transparent border-b border-white/10 rounded-none h-auto p-0 w-full justify-start">
            {[
              ["power", "Power"],
              ["snapshots", "Snapshots"],
            ].map(([v, l]) => (
              <TabsTrigger
                key={v}
                value={v}
                data-testid={`tab-${v}`}
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-accent-brand data-[state=active]:bg-transparent data-[state=active]:text-white text-neutral-400 py-3 px-5 font-medium"
              >
                {l}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="power" className="pt-6">
            <PowerPanel
              droplet={droplet}
              onChanged={load}
              onReinstallStarted={(meta) => {
                setReinstallState(meta);
                toast.success("Reinstall started. Live progress polling enabled.");
              }}
            />
          </TabsContent>
          <TabsContent value="snapshots" className="pt-6">
            <SnapshotsPanel dropletId={droplet.id} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

function Spec({ label, value, mono, accent }) {
  return (
    <div className="p-5 border-r border-b border-white/10 last:border-r-0">
      <div className="overline mb-1.5">{label}</div>
      <div
        className={`${mono ? "font-mono" : "font-heading font-bold"} ${
          accent ? "text-accent-brand" : "text-white"
        } text-lg`}
      >
        {value || "—"}
      </div>
    </div>
  );
}
