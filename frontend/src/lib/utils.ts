import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

const LOCALE = "en-US";
const nf = (d: number) => new Intl.NumberFormat(LOCALE, { minimumFractionDigits: d, maximumFractionDigits: d });
export const fmt = (v: number | null | undefined, d = 1) => (v == null ? "—" : nf(d).format(v));
export const fmtHa = (v: number | null | undefined, d = 1) => `${fmt(v, d)} ha`;
export const fmtPct = (v: number | null | undefined, d = 1) => `${fmt(v, d)}%`;
export const fmtDate = (iso: string, opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", year: "numeric" }) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString(LOCALE, opts);
export const fmtDayMonth = (iso: string) => fmtDate(iso, { month: "short", day: "numeric" });

// Brazilian scenario: amounts stay in BRL (R$), formatted in English
const brl = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
export const fmtBRL = (v: number | null | undefined) => (v == null ? "—" : `R$ ${brl.format(v)}`);
export const fmtBRLk = (v: number) => (Math.abs(v) >= 1000 ? `R$ ${fmt(v / 1000, 1)}k` : fmtBRL(v));
