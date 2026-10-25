"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, ClipboardCheck, LayoutDashboard, LineChart, Map, Settings, Sprout, Wheat } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Visão Geral", icon: LayoutDashboard, ready: false },
  { href: "/mapa", label: "Mapa", icon: Map, ready: true },
  { href: "/talhoes", label: "Talhões", icon: Wheat, ready: false },
  { href: "/copiloto", label: "Copiloto", icon: Bot, ready: false },
  { href: "/tarefas", label: "Tarefas", icon: ClipboardCheck, ready: false },
  { href: "/resultados", label: "Resultados", icon: LineChart, ready: false },
  { href: "/configuracoes", label: "Configurações", icon: Settings, ready: false },
];

export function AppSidebar() {
  const path = usePathname();
  return (
    <aside className="hidden w-60 shrink-0 flex-col bg-navy-950 text-slate-300 md:flex">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="grid size-8 place-items-center rounded-lg bg-brand-500 text-white">
          <Sprout className="size-4.5" />
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight text-white">AgroCopilot</div>
          <div className="text-[11px] text-slate-400">Copiloto operacional</div>
        </div>
      </div>
      <nav className="mt-2 flex flex-col gap-0.5 px-3">
        {NAV.map(({ href, label, icon: Icon, ready }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          const cls = cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition",
            active ? "bg-navy-800 text-white" : "hover:bg-navy-900 hover:text-white",
            !ready && "pointer-events-none opacity-45",
          );
          const inner = (
            <>
              <Icon className={cn("size-4", active && "text-brand-500")} />
              <span className="flex-1">{label}</span>
              {!ready && <span className="rounded bg-navy-800 px-1.5 py-px text-[10px] text-slate-400">em breve</span>}
            </>
          );
          return ready ? <Link key={href} href={href} className={cls}>{inner}</Link> : <div key={href} className={cls} aria-disabled>{inner}</div>;
        })}
      </nav>
      <div className="mt-auto border-t border-navy-800 px-5 py-4 text-[11px] leading-relaxed text-slate-500">
        MVP de demonstração. Índices de satélite direcionam vistorias — não são diagnóstico.
      </div>
    </aside>
  );
}
