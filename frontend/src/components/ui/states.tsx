import { AlertTriangle, Loader2 } from "lucide-react";

export function Loading({ label = "Carregando…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-4 text-sm text-slate-500">
      <Loader2 className="size-4 animate-spin" /> {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="m-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
      <div className="flex items-center gap-2 font-medium"><AlertTriangle className="size-4" /> Não foi possível carregar</div>
      <p className="mt-1 text-red-600/90">{error instanceof Error ? error.message : String(error)}</p>
      {onRetry && <button onClick={onRetry} className="mt-2 text-xs font-medium underline">Tentar novamente</button>}
    </div>
  );
}
