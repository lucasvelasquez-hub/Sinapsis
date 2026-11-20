"use client";

import { UserRound } from "lucide-react";
import { useEffect } from "react";

import { cn } from "@/lib/utils";
import { normalizeDispatcherId, useDispatcherStore } from "@/stores/dispatcherStore";

/** Identificador del despachador: obligatorio para registrar cualquier decisión. */
export function DispatcherField() {
  const { dispatcherId, setDispatcherId } = useDispatcherStore();

  useEffect(() => {
    void useDispatcherStore.persist.rehydrate();
  }, []);

  const valid = normalizeDispatcherId(dispatcherId) !== null;

  return (
    <label className="flex flex-col gap-1 text-[11px] text-slate-400">
      <span className="inline-flex items-center gap-1 uppercase tracking-wider">
        <UserRound className="h-3 w-3" />
        Despachador
      </span>
      <input
        type="text"
        value={dispatcherId}
        onChange={(e) => setDispatcherId(e.target.value)}
        placeholder="p. ej. desp-07"
        aria-invalid={!valid}
        className={cn(
          "w-44 rounded border bg-slate-950 px-2 py-1 text-xs text-white",
          valid ? "border-slate-700" : "border-amber-500/60"
        )}
      />
      {!valid && (
        <span className="text-amber-300">Obligatorio para decidir (2-64, sin espacios)</span>
      )}
    </label>
  );
}
