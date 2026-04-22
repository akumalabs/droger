import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
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
import { Checkbox } from "./ui/checkbox";
import { toast } from "sonner";

export default function CreateDropletDialog({ open, onOpenChange, onCreated }) {
  const [form, setForm] = useState({
    name: "",
    region: "",
    size: "",
    image: "ubuntu-22-04-x64",
    ssh_keys: [],
  });
  const [regions, setRegions] = useState([]);
  const [sizes, setSizes] = useState([]);
  const [images, setImages] = useState([]);
  const [sshKeys, setSshKeys] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const [r, s, i, k] = await Promise.all([
          api.get("/do/regions"),
          api.get("/do/sizes"),
          api.get("/do/images"),
          api.get("/do/ssh_keys"),
        ]);
        setRegions((r.data.regions || []).filter((x) => x.available));
        setSizes((s.data.sizes || []).filter((x) => x.available));
        setImages(i.data.images || []);
        setSshKeys(k.data.ssh_keys || []);
      } catch (e) {
        toast.error("Failed to load droplet options");
      }
    })();
  }, [open]);

  const submit = async () => {
    if (!form.name || !form.region || !form.size || !form.image) {
      toast.error("Fill all required fields");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/do/droplets", form);
      toast.success("Droplet creation started");
      onCreated?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Create failed");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleKey = (id) => {
    setForm((f) => ({
      ...f,
      ssh_keys: f.ssh_keys.includes(id)
        ? f.ssh_keys.filter((k) => k !== id)
        : [...f.ssh_keys, id],
    }));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="bg-[#0f0f10] border-white/10 rounded-none max-w-2xl max-h-[90vh] overflow-y-auto"
        data-testid="create-droplet-dialog"
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl font-bold">
            Spin up a droplet
          </DialogTitle>
          <DialogDescription className="text-neutral-400">
            Provision a new DigitalOcean droplet. Install Windows after boot
            from the droplet detail page.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5 py-4">
          <Field label="Hostname">
            <Input
              data-testid="new-name"
              placeholder="my-server-01"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="bg-black border-white/10 rounded-none font-mono"
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Region">
              <Select value={form.region} onValueChange={(v) => setForm({ ...form, region: v })}>
                <SelectTrigger data-testid="new-region" className="bg-black border-white/10 rounded-none">
                  <SelectValue placeholder="Select region" />
                </SelectTrigger>
                <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none">
                  {regions.map((r) => (
                    <SelectItem key={r.slug} value={r.slug}>
                      {r.name} ({r.slug})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>

            <Field label="Distribution">
              <Select value={form.image} onValueChange={(v) => setForm({ ...form, image: v })}>
                <SelectTrigger data-testid="new-image" className="bg-black border-white/10 rounded-none">
                  <SelectValue placeholder="Select image" />
                </SelectTrigger>
                <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none max-h-60">
                  {images.map((img) => (
                    <SelectItem key={img.slug || img.id} value={img.slug || String(img.id)}>
                      {img.distribution} {img.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>

          <Field label="Size">
            <Select value={form.size} onValueChange={(v) => setForm({ ...form, size: v })}>
              <SelectTrigger data-testid="new-size" className="bg-black border-white/10 rounded-none">
                <SelectValue placeholder="Select size" />
              </SelectTrigger>
              <SelectContent className="bg-[#0f0f10] border-white/10 rounded-none max-h-60">
                {sizes
                  .filter((s) => !form.region || s.regions.includes(form.region))
                  .map((s) => (
                    <SelectItem key={s.slug} value={s.slug}>
                      {s.slug} — {s.vcpus} vCPU · {s.memory}MB · ${s.price_monthly}/mo
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </Field>

          {sshKeys.length > 0 && (
            <Field label={`SSH keys (${sshKeys.length})`}>
              <div className="border border-white/10 p-3 max-h-36 overflow-y-auto space-y-2">
                {sshKeys.map((k) => (
                  <label
                    key={k.id}
                    className="flex items-center gap-2 text-sm cursor-pointer"
                  >
                    <Checkbox
                      checked={form.ssh_keys.includes(k.id)}
                      onCheckedChange={() => toggleKey(k.id)}
                      className="rounded-none"
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
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="rounded-none border-white/10"
          >
            Cancel
          </Button>
          <Button
            data-testid="submit-create"
            onClick={submit}
            disabled={submitting}
            className="rounded-none bg-white text-black hover:bg-neutral-200"
          >
            {submitting ? "Creating…" : "Create droplet"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
