"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowUp, Bot, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { CopilotResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AnswerCard } from "./answer-card";

type Msg = { role: "user"; content: string } | { role: "assistant"; content: string; r: CopilotResponse } | { role: "error"; content: string };

export function CopilotChat({ fieldId, fieldCode, source, compact = false }: { fieldId?: number | null; fieldCode?: string; source: string; compact?: boolean }) {
  const status = useQuery({ queryKey: ["copilot-status"], queryFn: api.copilotStatus });
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const end = useRef<HTMLDivElement>(null);

  const m = useMutation({
    mutationFn: (q: string) => {
      const history = msgs.filter((x) => x.role !== "error").map((x) => ({ role: x.role, content: x.content }));
      return api.ask(q, history, fieldId);
    },
    onSuccess: (r) => setMsgs((p) => [...p, { role: "assistant", content: r.answer.resumo, r }]),
    onError: (e) => setMsgs((p) => [...p, { role: "error", content: (e as Error).message }]),
  });

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, m.isPending]);

  const send = (q: string) => {
    const text = q.trim();
    if (!text || m.isPending) return;
    setMsgs((p) => [...p, { role: "user", content: text }]);
    setInput("");
    m.mutate(text);
  };

  const suggestions = (status.data?.suggestions ?? []).map((s) => (fieldCode ? s.replace(/Talhão 04|T04/g, fieldCode) : s));

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className={cn("min-h-0 flex-1 space-y-4 overflow-y-auto", compact ? "p-4" : "px-6 py-6")}>
        {msgs.length === 0 && (
          <div className={cn("mx-auto", compact ? "" : "max-w-2xl pt-6")}>
            <div className="flex items-center gap-3">
              <div className="grid size-10 place-items-center rounded-xl bg-navy-900 text-brand-500"><Bot className="size-5" /></div>
              <div>
                <div className="text-sm font-semibold text-slate-900">Copiloto da fazenda</div>
                <div className="text-xs text-slate-500">Responde com dados do app: evidências, confiança, o que falta e a próxima ação.</div>
              </div>
            </div>
            <div className="mt-5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Experimente perguntar</div>
            <div className={cn("mt-2 grid gap-2", compact ? "" : "sm:grid-cols-2")}>
              {suggestions.map((s) => (
                <button key={s} onClick={() => send(s)} className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white p-3 text-left text-xs text-slate-700 transition hover:border-brand-500/50 hover:bg-brand-50/40">
                  <Sparkles className="mt-0.5 size-3.5 shrink-0 text-brand-600" />{s}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className={cn("space-y-4", !compact && "mx-auto max-w-3xl")}>
          {msgs.map((x, i) =>
            x.role === "user" ? (
              <div key={i} className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-navy-900 px-3.5 py-2 text-[13px] text-white">{x.content}</div></div>
            ) : x.role === "assistant" ? (
              <div key={i} className="flex gap-2">
                {!compact && <div className="mt-1 grid size-7 shrink-0 place-items-center rounded-lg bg-navy-900 text-brand-500"><Bot className="size-4" /></div>}
                <div className="min-w-0 flex-1"><AnswerCard r={x.r} source={source} /></div>
              </div>
            ) : (
              <div key={i} className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">Não consegui responder: {x.content}</div>
            ),
          )}
          {m.isPending && (
            <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="size-3.5 animate-spin" /> Consultando dados da fazenda…</div>
          )}
          <div ref={end} />
        </div>
      </div>

      <div className={cn("border-t border-slate-200 bg-white", compact ? "p-3" : "px-6 py-4")}>
        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className={cn("flex items-end gap-2", !compact && "mx-auto max-w-3xl")}>
          {msgs.length > 0 && (
            <button type="button" onClick={() => setMsgs([])} title="Nova conversa" className="grid size-9 shrink-0 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"><RotateCcw className="size-4" /></button>
          )}
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
            rows={1}
            placeholder={fieldCode ? `Pergunte sobre o ${fieldCode} ou a fazenda…` : "Pergunte sobre a fazenda…"}
            className="max-h-32 min-h-9 flex-1 resize-none rounded-lg border border-slate-200 px-3 py-2 text-[13px] outline-none focus:ring-2 focus:ring-brand-500/30"
          />
          <button type="submit" disabled={!input.trim() || m.isPending} aria-label="Enviar" className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-600 text-white transition hover:bg-brand-700 disabled:opacity-40"><ArrowUp className="size-4" /></button>
        </form>
        <p className={cn("mt-1.5 text-[10px] text-slate-400", !compact && "mx-auto max-w-3xl")}>
          {status.data?.label ?? "…"} · Consultivo: não cria tarefas sem sua confirmação. Dados de demonstração.
        </p>
      </div>
    </div>
  );
}
