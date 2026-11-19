import Link from "next/link";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6">
      <div className="w-full max-w-md rounded-lg border border-slate-800 bg-slate-900 p-8">
        <h1 className="font-mono text-xl font-bold tracking-widest text-white">
          CORE MVP v1.0
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Acceso operacional de demostración (autenticación fuera del camino crítico del MVP).
        </p>
        <Link
          href="/dispatch"
          className="mt-6 block w-full rounded-md bg-cyan-600 px-4 py-2.5 text-center text-sm font-semibold text-white hover:bg-cyan-500"
        >
          Ingresar al Dispatch Center
        </Link>
      </div>
    </div>
  );
}
