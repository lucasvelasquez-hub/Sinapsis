import { cn } from "@/lib/utils";

export type DataProvenance = "OBSERVADO" | "CALCULADO" | "PREDICHO" | "SIMULADO";

const STYLES: Record<DataProvenance, string> = {
  OBSERVADO: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  CALCULADO: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  PREDICHO: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  SIMULADO: "border-violet-500/40 bg-violet-500/10 text-violet-300",
};

export function ProvenanceBadge({
  type,
  className,
}: {
  type: DataProvenance;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wider uppercase",
        STYLES[type],
        className
      )}
    >
      {type}
    </span>
  );
}
