"use client";
import * as S from "@radix-ui/react-slider";
import { cn } from "@/lib/utils";

export function Slider({ className, ...p }: React.ComponentProps<typeof S.Root>) {
  return (
    <S.Root className={cn("relative flex h-4 w-full touch-none select-none items-center", className)} {...p}>
      <S.Track className="relative h-1 grow rounded-full bg-slate-200">
        <S.Range className="absolute h-full rounded-full bg-brand-500" />
      </S.Track>
      <S.Thumb aria-label={p["aria-label"]} className="block size-3.5 rounded-full border-2 border-brand-600 bg-white shadow focus:outline-none focus:ring-2 focus:ring-brand-500/40" />
    </S.Root>
  );
}
