import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import TopNav from "../components/TopNav";
import StatusBadge from "../components/StatusBadge";
import SnapshotsPanel from "../components/SnapshotsPanel";
import PowerPanel from "../components/PowerPanel";
import { Button } from "../components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { ArrowLeft, ArrowsClockwise, CheckCircle, CircleNotch } from "@phosphor-icons/react";
import { toast } from "sonner";
import { useDOTokens } from "../context/DOTokenContext";

export default function DropletDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { active } = useDOTokens();
  const pollRef = useRef(null);
  const [droplet, setDroplet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusReady, setStatusReady] = useState(false);
  const [statusError, setStatusError] = useState("");
  const [statusPublicIp, setStatusPublicIp] = useState("");
  const [pingOk, setPingOk] = useState(false);
  const [rdpOpen, setRdpOpen] = useState(false);
  const [installComplete, setInstallComplete] = useState(false);
  const [installMessage, setInstallMessage] = useState("");
  const [rdpPort, setRdpPort] = useState(null);
  const [rdpPassword, setRdpPassword] = useState("");

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
    if (!id) {
      setStatusLoading(false);
      setStatusReady(false);
      setStatusError("");
      setStatusPublicIp("");
      setPingOk(false);
      setRdpOpen(false);
      setInstallComplete(false);
      setInstallMessage("");
      setRdpPort(null);
      setRdpPassword("");
      return;
    }

    if (!active?.id) {
      setStatusLoading(false);
      setStatusReady(false);
      setStatusError("No active DigitalOcean token selected");
      setStatusPublicIp("");
      setPingOk(false);
      setRdpOpen(false);
      setInstallComplete(false);
      setInstallMessage("");
      setRdpPort(null);
      setRdpPassword("");
      return;
    }

    let stopped = false;
    const poll = async () => {
      try {
        setStatusLoading(true);
        const { data } = await api.get(`/wizard/progress/${id}`, {
          params: { token_id: active.id },
        });
        if (stopped) return;

        const nextPort =
          Number.isInteger(data.rdp_port) && data.rdp_port >= 1 && data.rdp_port <= 65535
            ? data.rdp_port
            : null;

        setStatusReady(true);
        setStatusError("");
        setStatusPublicIp(data.public_ip || "");
        setPingOk(Boolean(data.ping_ok));
        setRdpOpen(Boolean(data.rdp_open));
        setInstallComplete(Boolean(data.install_complete));
        setInstallMessage(data.install_message || "");
        setRdpPort(nextPort);
        setRdpPassword(data.rdp_password || "");
      } catch (e) {
        if (stopped) return;
        setStatusError(e?.response?.data?.detail || "Unable to fetch install status");
      } finally {
        if (stopped) return;
        setStatusLoading(false);
        pollRef.current = setTimeout(poll, 5000);
      }
    };

    setStatusReady(false);
    setStatusError("");
    setStatusPublicIp("");
    setPingOk(false);
    setRdpOpen(false);
    setInstallComplete(false);
    setInstallMessage("");
    setRdpPort(null);
    setRdpPassword("");
    poll();

    return () => {
      stopped = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [id, active?.id]);

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
  const imageDistribution = String(droplet.image?.distribution || "").trim();
  const imageName = String(droplet.image?.name || "").trim();
  const imageLabel =
    imageDistribution && imageName
      ? imageName.toLowerCase().startsWith(imageDistribution.toLowerCase())
        ? imageName
        : `${imageDistribution} ${imageName}`.trim()
      : imageName || imageDistribution || "—";
  const windowsPublicIp = statusPublicIp || (publicIp !== "—" ? publicIp : "—");
  const readyMessage =
    installMessage || "Windows has been installed, you should be able to access it now.";

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

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-0 border border-white/10 mb-10">
          <Spec label="VCPUS" value={droplet.vcpus} />
          <Spec label="MEMORY" value={`${droplet.memory} MB`} />
          <Spec label="DISK" value={`${droplet.disk} GB`} />
          <Spec
            label="IMAGE"
            value={imageLabel}
            mono
          />
          <Spec label="PUBLIC IPV4" value={publicIp} mono accent />
          <Spec label="PRIVATE IPV4" value={privateIp} mono />
          <Spec label="REGION" value={droplet.region?.slug?.toUpperCase()} mono />
          <Spec
            label="CREATED"
            value={new Date(droplet.created_at).toLocaleDateString()}
            mono
          />
        </div>

        <div className="border border-white/10 p-6 mb-10 space-y-4">
          <p className="overline mb-1">WINDOWS INSTALL STATUS</p>

          {installComplete && (
            <div className="text-xs text-green-400 font-mono border border-green-500/30 p-3 flex items-center gap-2">
              <CheckCircle size={14} weight="fill" />
              {readyMessage}
            </div>
          )}

          {!installComplete && (
            <div className="text-xs text-neutral-400 font-mono flex flex-wrap items-center gap-2">
              {statusLoading && !statusReady && <CircleNotch className="animate-spin" size={14} />}
              <span>Connectivity checks</span>
              <span>·</span>
              <span>ICMP: {pingOk ? "OK" : "waiting"}</span>
              <span>·</span>
              <span>RDP {rdpPort ?? "—"}: {rdpOpen ? "OPEN" : "waiting"}</span>
            </div>
          )}

          {statusError && (
            <div className="text-xs text-red-400 font-mono border border-red-500/30 p-3">{statusError}</div>
          )}

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-0 border border-white/10">
            <Spec label="IP" value={windowsPublicIp} mono accent />
            <Spec label="USERNAME" value="Administrator" mono />
            <Spec label="PASSWORD" value={rdpPassword || "—"} mono />
            <Spec label="PORT" value={rdpPort} mono />
          </div>
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
