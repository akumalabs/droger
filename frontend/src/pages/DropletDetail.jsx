import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import TopNav from "../components/TopNav";
import StatusBadge from "../components/StatusBadge";
import WindowsInstallPanel from "../components/WindowsInstallPanel";
import SnapshotsPanel from "../components/SnapshotsPanel";
import PowerPanel from "../components/PowerPanel";
import { Button } from "../components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { ArrowLeft, ArrowsClockwise, Terminal } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function DropletDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [droplet, setDroplet] = useState(null);
  const [loading, setLoading] = useState(true);

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

  const consoleUrl = `https://cloud.digitalocean.com/droplets/${droplet.id}/terminal/ui`;

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
            <a href={consoleUrl} target="_blank" rel="noreferrer">
              <Button
                data-testid="open-console"
                className="rounded-none bg-white text-black hover:bg-neutral-200"
              >
                <Terminal size={16} className="mr-2" weight="bold" /> Console
              </Button>
            </a>
          </div>
        </div>

        {/* Specs grid */}
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
              ["reinstall", "Install Windows"],
              ["snapshots", "Snapshots"],
              ["console", "Console"],
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
            <PowerPanel droplet={droplet} onChanged={load} />
          </TabsContent>
          <TabsContent value="reinstall" className="pt-6">
            <WindowsInstallPanel droplet={droplet} />
          </TabsContent>
          <TabsContent value="snapshots" className="pt-6">
            <SnapshotsPanel dropletId={droplet.id} />
          </TabsContent>
          <TabsContent value="console" className="pt-6">
            <ConsolePanel droplet={droplet} consoleUrl={consoleUrl} />
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

function ConsolePanel({ droplet, consoleUrl }) {
  return (
    <div className="border border-white/10 p-8 max-w-2xl">
      <h3 className="font-heading text-2xl font-bold mb-2">DigitalOcean Recovery Console</h3>
      <p className="text-sm text-neutral-400 mb-6">
        Open the DigitalOcean web console to paste the Windows install command
        or perform emergency recovery.
      </p>
      <div className="space-y-4 font-mono text-xs">
        <div className="flex justify-between border-b border-white/10 py-2">
          <span className="text-neutral-500">DROPLET ID</span>
          <span>{droplet.id}</span>
        </div>
        <div className="flex justify-between border-b border-white/10 py-2">
          <span className="text-neutral-500">PUBLIC IP</span>
          <span className="text-accent-brand">
            {droplet.networks?.v4?.find((n) => n.type === "public")?.ip_address || "—"}
          </span>
        </div>
      </div>
      <a href={consoleUrl} target="_blank" rel="noreferrer" className="block mt-6">
        <Button
          data-testid="console-open-btn"
          className="rounded-none bg-white text-black hover:bg-neutral-200"
        >
          <Terminal size={16} className="mr-2" weight="bold" /> Open Console
        </Button>
      </a>
    </div>
  );
}
