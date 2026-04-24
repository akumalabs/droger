import React, { useCallback, useEffect, useMemo, useState } from "react";
import TopNav from "../components/TopNav";
import { api } from "../lib/api";
import { useDOTokens } from "../context/DOTokenContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Checkbox } from "../components/ui/checkbox";
import { ArrowsClockwise, CircleNotch, Rocket, TrashSimple } from "@phosphor-icons/react";
import { toast } from "sonner";

const STATUS_STYLES = {
  pending: "text-neutral-300 border-white/20 bg-white/5",
  transferring: "text-amber-300 border-amber-400/40 bg-amber-500/10",
  available: "text-emerald-300 border-emerald-400/40 bg-emerald-500/10",
  error: "text-red-300 border-red-400/40 bg-red-500/10",
};

function formatTime(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return "—";
  }
}

function StatusPill({ status }) {
  const key = String(status || "pending").toLowerCase();
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 border text-[10px] uppercase tracking-wide font-mono ${
        STATUS_STYLES[key] || STATUS_STYLES.pending
      }`}
    >
      {key}
    </span>
  );
}

export default function Templates() {
  const { tokens, active } = useDOTokens();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");
  const [deployOpen, setDeployOpen] = useState(false);
  const [deployTemplate, setDeployTemplate] = useState(null);

  const [targetTokenId, setTargetTokenId] = useState("");
  const [name, setName] = useState("");
  const [region, setRegion] = useState("");
  const [size, setSize] = useState("");
  const [regions, setRegions] = useState([]);
  const [sizes, setSizes] = useState([]);
  const [sshKeys, setSshKeys] = useState([]);
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [deploying, setDeploying] = useState(false);

  const tokenIds = useMemo(() => new Set(tokens.map((t) => t.id)), [tokens]);
  const availableSizes = useMemo(
    () => sizes.filter((s) => !region || s.regions?.includes(region)),
    [sizes, region],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/templates");
      setTemplates(data.templates || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!deployOpen) return;
    if (!targetTokenId) return;

    let stopped = false;
    setLoadingOptions(true);
    (async () => {
      try {
        const [r, s, k] = await Promise.all([
          api.get("/do/regions", { params: { token_id: targetTokenId } }),
          api.get("/do/sizes", { params: { token_id: targetTokenId } }),
          api.get("/do/ssh_keys", { params: { token_id: targetTokenId } }),
        ]);
        if (stopped) return;
        setRegions((r.data.regions || []).filter((x) => x.available));
        setSizes((s.data.sizes || []).filter((x) => x.available));
        setSshKeys(k.data.ssh_keys || []);
      } catch (e) {
        if (!stopped) {
          toast.error(e?.response?.data?.detail || "Failed to load deploy options");
        }
      } finally {
        if (!stopped) setLoadingOptions(false);
      }
    })();

    return () => {
      stopped = true;
    };
  }, [deployOpen, targetTokenId]);

  const syncNow = async (templateId, tokenId) => {
    const key = `sync:${templateId}:${tokenId}`;
    setBusyKey(key);
    try {
      await api.post(`/templates/${templateId}/sync`, { token_id: tokenId });
      toast.success("Template sync started");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Sync failed");
    } finally {
      setBusyKey("");
    }
  };

  const removeTemplate = async (templateId) => {
    const key = `delete:${templateId}`;
    setBusyKey(key);
    try {
      await api.delete(`/templates/${templateId}`);
      toast.success("Template removed");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    } finally {
      setBusyKey("");
    }
  };

  const openUseTemplate = (template, tokenId) => {
    const fallbackToken = tokenId || active?.id || tokens[0]?.id || "";
    setDeployTemplate(template);
    setTargetTokenId(fallbackToken);
    setName(`${template.label || "template"}-node`);
    setRegion("");
    setSize("");
    setSelectedKeys([]);
    setDeployOpen(true);
  };

  const toggleKey = (id) => {
    setSelectedKeys((prev) =>
      prev.includes(id) ? prev.filter((k) => k !== id) : [...prev, id],
    );
  };

  const deploy = async () => {
    if (!deployTemplate || !targetTokenId || !name || !region || !size) {
      toast.error("Fill all required deploy fields");
      return;
    }

    setDeploying(true);
    try {
      const { data } = await api.post(`/templates/${deployTemplate.id}/deploy`, {
        token_id: targetTokenId,
        name,
        region,
        size,
        ssh_keys: selectedKeys.length ? selectedKeys : null,
      });
      toast.success(`Droplet ${data?.droplet?.name || ""} creation started`);
      setDeployOpen(false);
      setDeployTemplate(null);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Deploy failed");
    } finally {
      setDeploying(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050505]">
      <TopNav />
      <main className="px-6 py-8 max-w-[1600px] mx-auto">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
          <div>
            <p className="overline text-accent-brand mb-3">LIBRARY // TEMPLATES</p>
            <h1 className="font-heading text-4xl sm:text-5xl font-black tracking-tight">
              Snapshot Templates
            </h1>
            <p className="text-sm text-neutral-400 mt-2">
              Save snapshots once, sync them across accounts, and deploy anywhere.
            </p>
          </div>
          <Button
            onClick={load}
            variant="outline"
            className="rounded-none border-white/10 hover:bg-white/5"
            data-testid="templates-refresh"
          >
            <ArrowsClockwise size={16} className="mr-2" /> Refresh
          </Button>
        </div>

        <div className="border border-white/10">
          {loading && (
            <div className="p-12 text-center text-neutral-500 font-mono text-sm">
              Loading templates…
            </div>
          )}

          {!loading && templates.length === 0 && (
            <div className="p-12 text-center text-neutral-500">
              No templates yet. Save one from a droplet snapshot.
            </div>
          )}

          {!loading &&
            templates.map((tpl) => (
              <div key={tpl.id} className="border-b border-white/10 last:border-b-0 p-5 space-y-4">
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="font-heading text-2xl font-black">{tpl.label || tpl.name}</h2>
                      <StatusPill status={tpl.status} />
                    </div>
                    <div className="text-xs font-mono text-neutral-500">
                      Template #{tpl.id} · Snapshot #{tpl.snapshot_id} · Current image #{tpl.current_image_id}
                    </div>
                    <div className="text-xs font-mono text-neutral-500">
                      Owner: {tpl.owner_token_name || tpl.owner_token_id} · {tpl.owner_account_uuid || "—"}
                    </div>
                    {tpl.notes && <div className="text-sm text-neutral-300">{tpl.notes}</div>}
                    {tpl.last_error && (
                      <div className="text-xs font-mono text-red-300 border border-red-500/30 px-2 py-1 inline-block">
                        {tpl.last_error}
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 flex-wrap">
                    <Button
                      variant="outline"
                      className="rounded-none border-white/10"
                      onClick={() => openUseTemplate(tpl, tpl.owner_token_id)}
                      data-testid={`use-owner-${tpl.id}`}
                    >
                      <Rocket size={14} className="mr-2" /> Use Template
                    </Button>
                    <Button
                      variant="outline"
                      className="rounded-none border-red-500/40 text-red-300 hover:bg-red-500/10"
                      onClick={() => removeTemplate(tpl.id)}
                      disabled={busyKey === `delete:${tpl.id}`}
                      data-testid={`delete-template-${tpl.id}`}
                    >
                      <TrashSimple size={14} className="mr-2" /> Delete
                    </Button>
                  </div>
                </div>

                <div className="border border-white/10 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10 text-left">
                        <th className="px-3 py-2 overline">Account</th>
                        <th className="px-3 py-2 overline">Status</th>
                        <th className="px-3 py-2 overline">Image</th>
                        <th className="px-3 py-2 overline">Last Sync</th>
                        <th className="px-3 py-2 overline">Error</th>
                        <th className="px-3 py-2 overline text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(tpl.availability || []).map((row) => {
                        const canUseToken = tokenIds.has(row.token_id);
                        const syncBusy = busyKey === `sync:${tpl.id}:${row.token_id}`;
                        return (
                          <tr key={`${tpl.id}:${row.token_id}`} className="border-b border-white/10 last:border-b-0">
                            <td className="px-3 py-3">
                              <div className="font-medium">{row.token_name || row.token_id}</div>
                              <div className="text-[11px] text-neutral-500 font-mono">{row.account_uuid || "—"}</div>
                            </td>
                            <td className="px-3 py-3">
                              <StatusPill status={row.status} />
                            </td>
                            <td className="px-3 py-3 font-mono text-xs">{row.image_id || "—"}</td>
                            <td className="px-3 py-3 font-mono text-xs">{formatTime(row.last_synced_at)}</td>
                            <td className="px-3 py-3 text-xs text-red-300 max-w-[280px] truncate">{row.last_error || "—"}</td>
                            <td className="px-3 py-3">
                              <div className="flex justify-end gap-2 flex-wrap">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="rounded-none border-white/10"
                                  onClick={() => openUseTemplate(tpl, row.token_id)}
                                  disabled={!canUseToken}
                                  data-testid={`use-template-${tpl.id}-${row.token_id}`}
                                >
                                  Use Template
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="rounded-none border-white/10"
                                  onClick={() => syncNow(tpl.id, row.token_id)}
                                  disabled={!canUseToken || syncBusy}
                                  data-testid={`sync-template-${tpl.id}-${row.token_id}`}
                                >
                                  {syncBusy ? (
                                    <span className="flex items-center gap-1">
                                      <CircleNotch size={12} className="animate-spin" /> Syncing
                                    </span>
                                  ) : (
                                    "Sync Now"
                                  )}
                                </Button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
        </div>
      </main>

      <Dialog
        open={deployOpen}
        onOpenChange={(open) => {
          setDeployOpen(open);
          if (!open) {
            setDeployTemplate(null);
            setDeploying(false);
          }
        }}
      >
        <DialogContent className="bg-[#0f0f10] border-white/10 rounded-none max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading text-2xl">
              Use template {deployTemplate?.label || deployTemplate?.name || ""}
            </DialogTitle>
            <DialogDescription className="text-neutral-400">
              Droger will sync the snapshot image to the selected account if it is not available yet.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label className="overline">Target account</Label>
              <Select
                value={targetTokenId}
                onValueChange={(value) => {
                  setTargetTokenId(value);
                  setRegion("");
                  setSize("");
                  setSelectedKeys([]);
                }}
              >
                <SelectTrigger className="bg-black border-white/10 rounded-none" data-testid="template-target-token">
                  <SelectValue placeholder="Select token" />
                </SelectTrigger>
                <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none">
                  {tokens.map((token) => (
                    <SelectItem key={token.id} value={token.id}>
                      {token.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="overline">Droplet name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="bg-black border-white/10 rounded-none font-mono"
                data-testid="template-droplet-name"
              />
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="overline">Region</Label>
                <Select value={region} onValueChange={setRegion} disabled={!targetTokenId || loadingOptions}>
                  <SelectTrigger className="bg-black border-white/10 rounded-none" data-testid="template-region">
                    <SelectValue placeholder={loadingOptions ? "Loading…" : "Select region"} />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none max-h-60">
                    {regions.map((r) => (
                      <SelectItem key={r.slug} value={r.slug}>
                        {r.name} ({r.slug})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label className="overline">Size</Label>
                <Select value={size} onValueChange={setSize} disabled={!region || loadingOptions}>
                  <SelectTrigger className="bg-black border-white/10 rounded-none" data-testid="template-size">
                    <SelectValue placeholder={region ? "Select size" : "Pick region first"} />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none max-h-60">
                    {availableSizes.map((s) => (
                      <SelectItem key={s.slug} value={s.slug}>
                        {s.slug} · {s.vcpus}vCPU/{s.memory}MB · ${s.price_monthly}/mo
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {sshKeys.length > 0 && (
              <div className="space-y-2">
                <Label className="overline">SSH keys (optional)</Label>
                <div className="border border-white/10 p-3 max-h-40 overflow-y-auto space-y-2">
                  {sshKeys.map((k) => (
                    <label key={k.id} className="flex items-center gap-2 text-sm cursor-pointer">
                      <Checkbox
                        checked={selectedKeys.includes(k.id)}
                        onCheckedChange={() => toggleKey(k.id)}
                        className="rounded-none"
                      />
                      <span className="font-mono text-xs">{k.name}</span>
                      <span className="text-neutral-500 text-xs truncate">{k.fingerprint}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeployOpen(false)}
              className="rounded-none border-white/10"
            >
              Cancel
            </Button>
            <Button
              onClick={deploy}
              disabled={deploying || !deployTemplate || !targetTokenId || !name || !region || !size}
              className="rounded-none bg-white text-black hover:bg-neutral-200"
              data-testid="confirm-template-deploy"
            >
              {deploying ? (
                <span className="flex items-center gap-2">
                  <CircleNotch size={14} className="animate-spin" /> Deploying
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Rocket size={14} /> Use Template
                </span>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
