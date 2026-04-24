import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
import TopNav from "../components/TopNav"
import { useDOTokens } from "../context/DOTokenContext"
import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog"
import { Plus, PencilSimple, TrashSimple, Check, X as XIcon } from "@phosphor-icons/react"
import { toast } from "sonner"

export default function Settings() {
  const { tokens, active, select, renameToken, deleteToken } = useDOTokens()
  const [editing, setEditing] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const navigate = useNavigate()

  const commitRename = async () => {
    if (!editing?.name.trim()) return
    try {
      await renameToken(editing.id, editing.name.trim())
      toast.success("Renamed")
      setEditing(null)
    } catch {
      toast.error("Rename failed")
    }
  }

  const doDelete = async (id) => {
    try {
      await deleteToken(id)
      toast.success("Token removed")
    } catch {
      toast.error("Delete failed")
    }
  }

  return (
    <div className="min-h-screen bg-[#050505]">
      <TopNav />
      <main className="px-6 py-10 max-w-4xl mx-auto">
        <p className="overline text-accent-brand mb-3">ACCOUNT // SETTINGS</p>
        <h1 className="font-heading text-4xl sm:text-5xl font-black tracking-tight mb-2">DigitalOcean accounts</h1>
        <p className="text-sm text-neutral-400 mb-8">
          Manage the DO API tokens linked to your account. Tokens are encrypted at rest and only decrypted in memory for outgoing DO calls.
        </p>

        <div className="flex justify-end mb-4">
          <Button
            onClick={() => navigate("/settings?add=1")}
            data-testid="settings-add-token"
            className="rounded-none bg-white text-black hover:bg-neutral-200"
          >
            <Plus size={16} className="mr-2" weight="bold" /> Add token
          </Button>
        </div>

        <div className="border border-white/10">
          {tokens.length === 0 && <div className="p-12 text-center text-neutral-500">No DO tokens yet. Add one to start managing droplets.</div>}
          {tokens.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-4 p-4 border-b border-white/10 last:border-b-0 hover:bg-white/5"
              data-testid={`token-row-${t.id}`}
            >
              <div className="flex-1 min-w-0">
                {editing?.id === t.id ? (
                  <div className="flex items-center gap-2">
                    <Input
                      autoFocus
                      value={editing.name}
                      onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                      className="bg-black border-white/10 rounded-none font-mono h-8 max-w-xs"
                      onKeyDown={(e) => e.key === "Enter" && commitRename()}
                    />
                    <Button size="icon" variant="ghost" onClick={commitRename} className="h-8 w-8">
                      <Check size={14} className="text-green-400" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => setEditing(null)} className="h-8 w-8">
                      <XIcon size={14} />
                    </Button>
                  </div>
                ) : (
                  <div className="font-medium flex items-center gap-2">
                    {t.name}
                    {active?.id === t.id && (
                      <span className="text-[10px] font-mono uppercase bg-accent-brand/10 text-accent-brand border border-accent-brand/30 px-1.5 py-0.5">
                        ACTIVE
                      </span>
                    )}
                  </div>
                )}
                <div className="text-xs font-mono text-neutral-500 mt-1">
                  {t.do_email || "—"} · {t.droplet_limit ?? "?"} droplet limit · added {new Date(t.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="flex gap-1">
                {active?.id !== t.id && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => select(t.id)}
                    className="rounded-none border-white/10"
                    data-testid={`activate-${t.id}`}
                  >
                    Activate
                  </Button>
                )}
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setEditing({ id: t.id, name: t.name })}
                  className="h-8 w-8"
                  data-testid={`rename-${t.id}`}
                >
                  <PencilSimple size={14} />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setConfirmDelete(t)}
                  className="h-8 w-8 text-red-400 hover:bg-red-500/10"
                  data-testid={`delete-token-${t.id}`}
                >
                  <TrashSimple size={14} />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </main>

      <AlertDialog open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <AlertDialogContent className="bg-[#0f0f10] border-white/10 rounded-none">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">Remove token “{confirmDelete?.name}”?</AlertDialogTitle>
            <AlertDialogDescription className="text-neutral-400">
              This removes the token from your vault. Your DigitalOcean account is not affected — you can re-add the token any time.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-none border-white/10">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirmDelete) doDelete(confirmDelete.id)
                setConfirmDelete(null)
              }}
              className="rounded-none bg-red-600 hover:bg-red-500"
              data-testid="confirm-delete-token"
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
