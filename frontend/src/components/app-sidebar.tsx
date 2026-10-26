"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Bot, ClipboardCheck, LayoutDashboard, LineChart, Map, Menu, Settings, Sprout, Wheat, X } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview", short: "Home", icon: LayoutDashboard },
  { href: "/map", label: "Map", short: "Map", icon: Map },
  { href: "/fields", label: "Fields", short: "Fields", icon: Wheat },
  { href: "/copilot", label: "Copilot", short: "Copilot", icon: Bot },
  { href: "/tasks", label: "Tasks", short: "Tasks", icon: ClipboardCheck },
  { href: "/outcomes", label: "Outcomes", short: "Outcomes", icon: LineChart },
  { href: "/settings", label: "Settings", short: "Settings", icon: Settings },
];
const MOBILE = ["/", "/map", "/tasks", "/copilot"];

const isActive = (path: string, href: string) => (href === "/" ? path === "/" : path.startsWith(href));

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid size-8 place-items-center rounded-lg bg-brand-500 text-white"><Sprout className="size-4.5" /></div>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight text-white">AgroCopilot</div>
        <div className="text-[11px] text-slate-400">Farm operations copilot</div>
      </div>
    </div>
  );
}

function NavList({ path, onNavigate }: { path: string; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5 px-3">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = isActive(path, href);
        return (
          <Link key={href} href={href} onClick={onNavigate}
            className={cn("flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition", active ? "bg-navy-800 text-white" : "hover:bg-navy-900 hover:text-white")}>
            <Icon className={cn("size-4", active && "text-brand-500")} />{label}
          </Link>
        );
      })}
    </nav>
  );
}

const FOOT = "Demo MVP. Satellite indices direct field inspections — they are not a diagnosis.";

export function AppSidebar() {
  const path = usePathname();
  return (
    <aside className="hidden w-60 shrink-0 flex-col bg-navy-950 text-slate-300 md:flex">
      <div className="px-5 py-5"><Logo /></div>
      <div className="mt-2"><NavList path={path} /></div>
      <div className="mt-auto border-t border-navy-800 px-5 py-4 text-[11px] leading-relaxed text-slate-500">{FOOT}</div>
    </aside>
  );
}

export function MobileNav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);
  return (
    <>
      <header className="flex items-center justify-between bg-navy-950 px-4 py-3 md:hidden">
        <Logo />
        <button onClick={() => setOpen(true)} aria-label="Open menu" className="rounded-lg p-1.5 text-slate-300 hover:bg-navy-800"><Menu className="size-5" /></button>
      </header>
      {open && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true">
          <button aria-label="Close menu" className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 right-0 flex w-72 flex-col bg-navy-950 text-slate-300 shadow-xl">
            <div className="flex items-center justify-between px-5 py-4"><Logo /><button onClick={() => setOpen(false)} aria-label="Close" className="rounded-lg p-1.5 hover:bg-navy-800"><X className="size-5" /></button></div>
            <NavList path={path} onNavigate={() => setOpen(false)} />
            <div className="mt-auto border-t border-navy-800 px-5 py-4 text-[11px] leading-relaxed text-slate-500">{FOOT}</div>
          </div>
        </div>
      )}
      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {NAV.filter((n) => MOBILE.includes(n.href)).map(({ href, short, icon: Icon }) => {
          const active = isActive(path, href);
          return (
            <Link key={href} href={href} className={cn("flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium", active ? "text-brand-700" : "text-slate-500")}>
              <Icon className="size-5" />{short}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
