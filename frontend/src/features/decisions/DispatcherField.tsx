"use client";

import { UserRound } from "lucide-react";
import { useEffect } from "react";

import { cn } from "@/lib/utils";
import { normalizeDispatcherId, useDispatcherStore } from "@/stores/dispatcherStore";

export const DISPATCHERS = [
  { id: "desp-01", label: "desp-01 · Despachador 1" },
  { id: "desp-02", label: "desp-02 · Despachador 2" },
  { id: "desp-03", label: "desp-03 · Despachador 3" },
  { id: "desp-04", label: "desp-04 · Despachador 4" },
  { id: "desp-05", label: "desp-05 · Despachador 5" },
  { id: "desp-06", label: "desp-06 · Despachador 6" },
  { id: "desp-07", label: "desp-07 · Despachador 7" },
] as const;

/** Identificador del despachador: obligatorio para registrar cualquier decisión. */
export function DispatcherField({ compact = false }: { compact?: boolean }) {
  const { dispatcherId, setDispatcherId } = useDispatcherStore();

  useEffect(() => {
    void useDispatcherStore.persist.rehydrate();
  }, []);

  const valid = normalizeDispatcherId(dispatcherId) !== null;
  const shortBadge = dispatcherId
    ? `D${dispatcherId.replace(/\D/g, "").replace(/^0+/, "") || dispatcherId.slice(0, 2).toUpperCase()}`
    : "--";

  if (compact) {
    return (
      <div className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/80 bg-[#071322] px-2 py-1">
        <span
          aria-hidden
          className={cn(
            "flex h-5 w-5 items-center justify-center rounded-full font-mono text-[10px] font-bold",
            valid
              ? "bg-sky-500/20 text-sky-300 ring-1 ring-sky-500/40"
              : "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40"
          )}
        >
          {shortBadge}
        </span>
        <select
          aria-label="Despachador activo"
          value={dispatcherId}
          onChange={(e) => setDispatcherId(e.target.value)}
          aria-invalid={!valid}
          className={cn(
            "max-w-[155px] cursor-pointer bg-transparent text-xs font-medium text-slate-100 focus:outline-none",
            !valid && "text-amber-200"
          )}
        >
          <option value="" className="bg-slate-950 text-slate-200">
            Despachador…
          </option>
          {DISPATCHERS.map((d) => (
            <option key={d.id} value={d.id} className="bg-slate-950 text-slate-100">
              {d.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <label className="flex flex-col gap-1 text-[11px] text-slate-400">
      <span className="inline-flex items-center gap-1 uppercase tracking-wider">
        <UserRound className="h-3 w-3" />
        Despachador
      </span>
      <select
        value={dispatcherId}
        onChange={(e) => setDispatcherId(e.target.value)}
        aria-invalid={!valid}
        className={cn(
          "w-48 rounded border bg-slate-950 px-2 py-1.5 text-xs text-white",
          valid ? "border-slate-700" : "border-amber-500/60"
        )}
      >
        <option value="">Selecciona despachador…</option>
        {DISPATCHERS.map((d) => (
          <option key={d.id} value={d.id}>
            {d.label}
          </option>
        ))}
      </select>
      {!valid && (
        <span className="text-amber-300">Obligatorio para decidir</span>
      )}
    </label>
  );
}
