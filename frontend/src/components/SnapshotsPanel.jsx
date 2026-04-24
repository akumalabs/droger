import React, { useCallback, useEffect, useState } from "react";
import { api, getActiveTokenId } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
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
import { Camera, TrashSimple, ArrowCounterClockwise, CopySimple } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function SnapshotsPanel({ dropletId }) {
  const [snaps, setSnaps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [confirmRestore, setConfirmRestore] = useState(null);
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
  const [templateSnap, setTemplateSnap] = useState(null);
  const [templateLabel, setTemplateLabel] = useState("");
  const [templateNotes, setTemplateNotes] = useState("");
  const [savingTemplate, setSavingTemplate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/do/droplets/${dropletId}/snapshots`);
      setSnaps(data.snapshots || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load snapshots");
    } finally {
      setLoading(false);
    }
  }, [dropletId]);

  useEffect(() => {
    load();
  }, [load]);

  const create = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.post(`/do/droplets/${dropletId}/snapshot`, { name: newName.trim() });
      toast.success("Snapshot started (takes a few minutes)");
      setNewName("");
      setCreateOpen(false);
      setTimeout(load, 4000);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Create failed");
    } finally {
      setCreating(false);
    }
  };

  const doDelete = async (snapId) => {
    try {
      await api.delete(`/do/snapshots/${snapId}`);
      toast.success("Snapshot deleted");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  const doRestore = async (snap) => {
    try {
      await api.post(`/do/droplets/${dropletId}/actions`, {
        action_type: "rebuild",
        image: String(snap.id),
      });
      toast.success("Rebuild from snapshot started");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Restore failed");
    }
  };

  const openSaveTemplate = (snap) => {
    setTemplateSnap(snap);
    setTemplateLabel(snap?.name || "");
    setTemplateNotes("");
    setSaveTemplateOpen(true);
  };

  const saveTemplate = async () => {
    if (!templateSnap || !templateLabel.trim()) return;
    const tokenId = getActiveTokenId();
    if (!tokenId) {
      toast.error("Select a DO token first");
      return;
    }

    setSavingTemplate(true);
    try {
      await api.post("/templates/from-snapshot", {
        token_id: tokenId,
        snapshot_id: Number(templateSnap.id),
        label: templateLabel.trim(),
        notes: templateNotes.trim() || null,
        source_droplet_id: Number(dropletId),
        snapshot_name: templateSnap.name || null,
      });
      toast.success("Template saved");
      setSaveTemplateOpen(false);
      setTemplateSnap(null);
      setTemplateLabel("");
      setTemplateNotes("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save template failed");
    } finally {
      setSavingTemplate(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="overline">SNAPSHOT VAULT · {snaps.length}</p>
        <Button
          onClick={() => setCreateOpen(true)}
          className="rounded-none bg-white text-black hover:bg-neutral-200"
          data-testid="create-snapshot-button"
        >
          <Camera size={16} className="mr-2" weight="bold" /> New Snapshot
        </Button>
      </div>

      <div className="border border-white/10">
        {loading && (
          <div className="p-8 text-neutral-500 font-mono text-sm text-center">
            Loading…
          </div>
        )}
        {!loading && snaps.length === 0 && (
          <div className="p-10 text-neutral-500 text-center">
            No snapshots yet. The droplet must be powered off for the most
            reliable snapshots.
          </div>
        )}
        {snaps.map((s) => (
          <div
            key={s.id}
            data-testid={`snapshot-${s.id}`}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 border-b border-white/10 last:border-b-0 hover:bg-white/5"
          >
            <div>
              <div className="font-medium">{s.name}</div>
              <div className="text-xs font-mono text-neutral-500">
                #{s.id} · {new Date(s.created_at).toLocaleString()} ·{" "}
                {s.size_gigabytes}GB
              </div>
            </div>
            <div className="flex gap-2 flex-wrap justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => openSaveTemplate(s)}
                className="rounded-none border-white/10"
                data-testid={`save-template-${s.id}`}
              >
                <CopySimple size={14} className="mr-1" /> Save as Template
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmRestore(s)}
                className="rounded-none border-white/10"
                data-testid={`restore-${s.id}`}
              >
                <ArrowCounterClockwise size={14} className="mr-1" /> Restore
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmDelete(s)}
                className="rounded-none border-white/10 text-red-400 hover:text-red-400 hover:bg-red-500/10"
                data-testid={`delete-${s.id}`}
              >
                <TrashSimple size={14} />
              </Button>
            </div>
          </div>
        ))}
      </div>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-[#0f0f10] border-white/10 rounded-none">
          <DialogHeader>
            <DialogTitle className="font-heading">Create snapshot</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label className="overline">Name</Label>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="pre-windows-baseline"
              className="bg-black border-white/10 rounded-none font-mono"
              data-testid="new-snapshot-name"
            />
            <p className="text-xs text-neutral-500">
              Power off the droplet first for a clean snapshot.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateOpen(false)}
              className="rounded-none border-white/10"
            >
              Cancel
            </Button>
            <Button
              onClick={create}
              disabled={creating || !newName.trim()}
              className="rounded-none bg-white text-black hover:bg-neutral-200"
              data-testid="confirm-create-snapshot"
            >
              {creating ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={saveTemplateOpen}
        onOpenChange={(open) => {
          setSaveTemplateOpen(open);
          if (!open) {
            setTemplateSnap(null);
            setTemplateLabel("");
            setTemplateNotes("");
          }
        }}
      >
        <DialogContent className="bg-[#0f0f10] border-white/10 rounded-none">
          <DialogHeader>
            <DialogTitle className="font-heading">Save as template</DialogTitle>
            <DialogDescription className="text-neutral-400">
              {templateSnap
                ? `Snapshot “${templateSnap.name}” will become reusable across accounts.`
                : "Create a reusable template from this snapshot."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label className="overline">Label</Label>
              <Input
                value={templateLabel}
                onChange={(e) => setTemplateLabel(e.target.value)}
                placeholder="Windows baseline"
                className="bg-black border-white/10 rounded-none font-mono"
                data-testid="template-label"
              />
            </div>
            <div className="space-y-2">
              <Label className="overline">Notes</Label>
              <Textarea
                value={templateNotes}
                onChange={(e) => setTemplateNotes(e.target.value)}
                placeholder="Patch level, software, credentials policy..."
                className="bg-black border-white/10 rounded-none font-mono min-h-[90px]"
                data-testid="template-notes"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSaveTemplateOpen(false)}
              className="rounded-none border-white/10"
            >
              Cancel
            </Button>
            <Button
              onClick={saveTemplate}
              disabled={savingTemplate || !templateLabel.trim()}
              className="rounded-none bg-white text-black hover:bg-neutral-200"
              data-testid="confirm-save-template"
            >
              {savingTemplate ? "Saving…" : "Save Template"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <AlertDialogContent className="bg-[#0f0f10] border-white/10 rounded-none">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">
              Delete snapshot “{confirmDelete?.name}”?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-neutral-400">
              This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-none border-white/10">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirmDelete) doDelete(confirmDelete.id);
                setConfirmDelete(null);
              }}
              className="rounded-none bg-red-600 hover:bg-red-500"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Restore confirm */}
      <AlertDialog open={!!confirmRestore} onOpenChange={(o) => !o && setConfirmRestore(null)}>
        <AlertDialogContent className="bg-[#0f0f10] border-white/10 rounded-none">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">
              Rebuild from “{confirmRestore?.name}”?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-neutral-400">
              This will overwrite the current disk of the droplet with the
              snapshot contents. All current data will be lost.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-none border-white/10">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirmRestore) doRestore(confirmRestore);
                setConfirmRestore(null);
              }}
              className="rounded-none bg-red-600 hover:bg-red-500"
            >
              Rebuild
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
