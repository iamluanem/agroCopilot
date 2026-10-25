import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

const nf = (d: number) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
export const fmt = (v: number | null | undefined, d = 1) => (v == null ? "—" : nf(d).format(v));
export const fmtHa = (v: number | null | undefined, d = 1) => `${fmt(v, d)} ha`;
export const fmtPct = (v: number | null | undefined, d = 1) => `${fmt(v, d)}%`;
export const fmtDate = (iso: string, opts: Intl.DateTimeFormatOptions = { day: "2-digit", month: "2-digit", year: "numeric" }) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("pt-BR", opts);

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
export const fmtBRL = (v: number | null | undefined) => (v == null ? "—" : brl.format(v));
export const fmtBRLk = (v: number) => (Math.abs(v) >= 1000 ? `R$ ${fmt(v / 1000, 1)} mil` : brl.format(v));
