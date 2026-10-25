"use client";
import { cn } from "@/lib/utils";

export function Segmented<T extends string>({
  value, onChange, options, className,
}: { value: T; onChange: (v: T) => void; options: { value: T; label: string; disabled?: boolean }[]; className?: string }) {
  return (
    <div className={cn("inline-flex rounded-lg bg-slate-100 p-0.5", className)} role="radiogroup">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          disabled={o.disabled}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium text-slate-600 transition",
            value === o.value ? "bg-white text-slate-900 shadow-sm" : "hover:text-slate-900",
            o.disabled && "cursor-not-allowed opacity-40",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
