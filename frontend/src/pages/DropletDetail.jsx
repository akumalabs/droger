import React, { useCallback, useEffect, useState } from "react";
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
import { ArrowLeft, ArrowsClockwise } from "@phosphor-icons/react";
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
  const imageDistribution = String(droplet.image?.distribution || "").trim();
  const imageName = String(droplet.image?.name || "").trim();
  const imageLabel =
    imageDistribution && imageName
      ? imageName.toLowerCase().startsWith(imageDistribution.toLowerCase())
        ? imageName
        : `${imageDistribution} ${imageName}`.trim()
      : imageName || imageDistribution || "—";

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
