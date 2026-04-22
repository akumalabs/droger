import React, { useState } from "react";
import { useDOTokens } from "../context/DOTokenContext";
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
import { toast } from "sonner";

export default function AddTokenDialog({ open, onOpenChange }) {
  const { addToken } = useDOTokens();
  const [name, setName] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim() || !token.trim()) {
      toast.error("Both fields are required");
      return;
    }
    setBusy(true);
    try {
      await addToken(name.trim(), token.trim());
      toast.success("Token saved & validated");
      setName("");
      setToken("");
      onOpenChange(false);
    } catch (e) {
      toast.error(
        typeof e?.response?.data?.detail === "string"
          ? e.response.data.detail
          : "Could not save token",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="bg-[#0f0f10] border-white/10 rounded-none max-w-md"
        data-testid="add-token-dialog"
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl font-bold">
            Add DigitalOcean token
          </DialogTitle>
          <DialogDescription className="text-neutral-400">
            Create a Personal Access Token at{" "}
            <a
              href="https://cloud.digitalocean.com/account/api/tokens"
              target="_blank"
              rel="noreferrer"
              className="text-accent-brand underline"
            >
              cloud.digitalocean.com
            </a>{" "}
            with read + write scope.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label className="overline">Nickname</Label>
            <Input
              data-testid="add-token-name"
              value={name}
              placeholder="Personal, Work, Client-X…"
              onChange={(e) => setName(e.target.value)}
              className="bg-black border-white/10 rounded-none font-mono"
            />
          </div>
          <div className="space-y-2">
            <Label className="overline">API Token</Label>
            <Input
              data-testid="add-token-value"
              type="password"
              value={token}
              placeholder="dop_v1_..."
              onChange={(e) => setToken(e.target.value)}
              className="bg-black border-white/10 rounded-none font-mono"
            />
            <p className="text-xs text-neutral-500">
              Token is validated with DO and encrypted at rest.
            </p>
          </div>
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
            data-testid="add-token-submit"
            onClick={submit}
            disabled={busy}
            className="rounded-none"
            style={{ background: "#00E5FF", color: "#000" }}
          >
            {busy ? "Validating…" : "Validate & Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
