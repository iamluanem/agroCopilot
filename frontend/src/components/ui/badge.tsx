import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badge = cva("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset", {
  variants: {
    tone: {
      neutral: "bg-slate-100 text-slate-700 ring-slate-200",
      demo: "bg-violet-50 text-violet-700 ring-violet-200",
      verde: "bg-emerald-50 text-emerald-700 ring-emerald-200",
      amarelo: "bg-amber-50 text-amber-800 ring-amber-200",
      vermelho: "bg-red-50 text-red-700 ring-red-200",
      sem_dado: "bg-slate-100 text-slate-600 ring-slate-200",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export function Badge({ className, tone, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ tone }), className)} {...p} />;
}
