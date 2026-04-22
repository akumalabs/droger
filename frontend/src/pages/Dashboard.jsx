import React, { useEffect, useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import TopNav from "../components/TopNav";
import CreateDropletDialog from "../components/CreateDropletDialog";
import StatusBadge from "../components/StatusBadge";
import { useDOTokens } from "../context/DOTokenContext";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { Button } from "../components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";
import {
  ArrowsClockwise,
  DotsThree,
  Power,
  Plus,
  TrashSimple,
  ArrowClockwise,
  Rocket,
  Key,
} from "@phosphor-icons/react";
import { toast } from "sonner";

export default function Dashboard() {
  const { active, tokens } = useDOTokens();
  const [droplets, setDroplets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    if (!active) {
      setDroplets([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.get("/do/droplets");
      setDroplets(data.droplets || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load droplets");
    } finally {
      setLoading(false);
    }
  }, [active?.id]);

  useEffect(() => {
    load();
  }, [load]);

  const doAction = async (id, action_type, successMsg) => {
    try {
      await api.post(`/do/droplets/${id}/actions`, { action_type });
      toast.success(successMsg);
      setTimeout(load, 1500);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Action failed");
    }
  };

  const doDelete = async (id) => {
    try {
      await api.delete(`/do/droplets/${id}`);
      toast.success("Droplet deleted");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  const publicIp = (d) =>
    d.networks?.v4?.find((n) => n.type === "public")?.ip_address || "—";

  // No DO tokens saved → empty state
  if (tokens.length === 0) {
    return (
      <div className="min-h-screen bg-[#050505]">
        <TopNav />
        <main className="px-6 py-24 max-w-xl mx-auto text-center">
          <Key size={40} className="mx-auto text-accent-brand mb-4" />
          <h1 className="font-heading text-4xl font-black mb-3">
            Add your first DO token
          </h1>
          <p className="text-neutral-400 mb-8">
            To list and manage droplets, link at least one DigitalOcean account
            to your profile. Tokens are encrypted at rest.
          </p>
          <Button
            onClick={() => navigate("/settings")}
            className="rounded-none bg-white text-black hover:bg-neutral-200"
            data-testid="empty-goto-settings"
          >
            <Plus size={16} className="mr-2" weight="bold" /> Add DO token
          </Button>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505]">
      <TopNav />
      <main className="px-6 py-8 max-w-[1600px] mx-auto">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-10">
          <div>
            <p className="overline text-accent-brand mb-3">NODE // FLEET</p>
            <h1 className="font-heading text-4xl sm:text-5xl font-black tracking-tight">
              Droplets
            </h1>
            <p className="text-sm text-neutral-400 mt-2">
              {active ? (
                <>
                  Token{" "}
                  <span className="font-mono text-accent-brand">{active.name}</span>
                  {" · "}
                  {droplets.length} droplets · {active.droplet_limit ?? "—"} limit
                </>
              ) : (
                "Select a token in the top bar"
              )}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              data-testid="refresh-button"
              onClick={load}
              variant="outline"
              className="rounded-none border-white/10 hover:bg-white/5"
            >
              <ArrowsClockwise size={16} className="mr-2" /> Refresh
            </Button>
            <Link to="/deploy">
              <Button
                data-testid="goto-wizard-button"
                variant="outline"
                className="rounded-none border-white/10 hover:bg-white/5"
              >
                <Rocket size={16} className="mr-2" weight="bold" /> Deploy Windows
              </Button>
            </Link>
            <Button
              data-testid="create-droplet-button"
              onClick={() => setCreateOpen(true)}
              className="rounded-none bg-white text-black hover:bg-neutral-200"
            >
              <Plus size={16} className="mr-2" weight="bold" /> New Droplet
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-0 mb-10 border border-white/10">
          <StatCard label="TOTAL" value={droplets.length} />
          <StatCard
            label="ACTIVE"
            value={droplets.filter((d) => d.status === "active").length}
            accent="#34D399"
          />
          <StatCard
            label="OFF"
            value={droplets.filter((d) => d.status === "off").length}
            accent="#FB7185"
          />
          <StatCard
            label="TRANSITIONING"
            value={droplets.filter((d) => d.status === "new").length}
            accent="#FBBF24"
          />
        </div>

        <div className="border border-white/10 bg-[#0a0a0b]">
          <Table>
            <TableHeader>
              <TableRow className="border-white/10 hover:bg-transparent">
                <TableHead className="overline h-10">Name</TableHead>
                <TableHead className="overline h-10">Status</TableHead>
                <TableHead className="overline h-10">Region</TableHead>
                <TableHead className="overline h-10">Size</TableHead>
                <TableHead className="overline h-10">Public IP</TableHead>
                <TableHead className="overline h-10">Image</TableHead>
                <TableHead className="overline h-10 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && (
                <TableRow className="border-white/10">
                  <TableCell colSpan={7} className="text-center py-12 text-neutral-500 font-mono text-sm">
                    Loading droplets…
                  </TableCell>
                </TableRow>
              )}
              {!loading && droplets.length === 0 && (
                <TableRow className="border-white/10">
                  <TableCell colSpan={7} className="text-center py-16 text-neutral-500">
                    No droplets on this account. Create one to get started.
                  </TableCell>
                </TableRow>
              )}
              {droplets.map((d) => (
                <TableRow
                  key={d.id}
                  className="border-white/10 hover:bg-white/5"
                  data-testid={`droplet-row-${d.id}`}
                >
                  <TableCell className="py-3">
                    <Link
                      to={`/droplets/${d.id}`}
                      className="font-medium hover:text-accent-brand transition-colors"
                      data-testid={`droplet-link-${d.id}`}
                    >
                      {d.name}
                    </Link>
                    <div className="text-xs font-mono text-neutral-500">#{d.id}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={d.status} />
                  </TableCell>
                  <TableCell className="font-mono text-xs text-neutral-300">
                    {d.region?.slug?.toUpperCase()}
                  </TableCell>
                  <TableCell className="font-mono text-xs">{d.size_slug}</TableCell>
                  <TableCell className="font-mono text-xs text-accent-brand">
                    {publicIp(d)}
                  </TableCell>
                  <TableCell className="text-xs text-neutral-400">
                    {d.image?.distribution} {d.image?.name || ""}
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          data-testid={`row-menu-${d.id}`}
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 hover:bg-white/10"
                        >
                          <DotsThree size={18} weight="bold" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent
                        align="end"
                        className="bg-[#0f0f10] border-white/10 rounded-none font-mono text-xs"
                      >
                        <DropdownMenuItem asChild>
                          <Link to={`/droplets/${d.id}`}>Open</Link>
                        </DropdownMenuItem>
                        <DropdownMenuSeparator className="bg-white/10" />
                        {d.status !== "active" && (
                          <DropdownMenuItem
                            onClick={() => doAction(d.id, "power_on", "Powering on")}
                          >
                            <Power size={14} className="mr-2" /> Power On
                          </DropdownMenuItem>
                        )}
                        {d.status === "active" && (
                          <>
                            <DropdownMenuItem
                              onClick={() => doAction(d.id, "reboot", "Rebooting")}
                            >
                              <ArrowClockwise size={14} className="mr-2" /> Reboot
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() =>
                                doAction(d.id, "power_off", "Powering off")
                              }
                            >
                              <Power size={14} className="mr-2" /> Power Off
                            </DropdownMenuItem>
                          </>
                        )}
                        <DropdownMenuSeparator className="bg-white/10" />
                        <DropdownMenuItem
                          className="text-red-400 focus:text-red-400"
                          onClick={() =>
                            setConfirm({ id: d.id, name: d.name, action: "delete" })
                          }
                        >
                          <TrashSimple size={14} className="mr-2" /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </main>

      <CreateDropletDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={load}
      />

      <AlertDialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <AlertDialogContent className="bg-[#0f0f10] border-white/10 rounded-none">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">
              Delete droplet “{confirm?.name}”?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-neutral-400">
              This permanently destroys the droplet and its data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-none border-white/10">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-delete"
              onClick={() => {
                if (confirm) doDelete(confirm.id);
                setConfirm(null);
              }}
              className="rounded-none bg-red-600 hover:bg-red-500 text-white"
            >
              Destroy
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function StatCard({ label, value, accent }) {
  return (
    <div className="p-6 border-r border-white/10 last:border-r-0">
      <div className="overline mb-2">{label}</div>
      <div
        className="font-heading text-4xl font-black"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
    </div>
  );
}
