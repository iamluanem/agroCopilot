import { FlaskConical } from "lucide-react";
import { Badge } from "./badge";

export function DemoBadge({ label = "Dados de demonstração", className }: { label?: string; className?: string }) {
  return (
    <Badge tone="demo" className={className} title="Dados sintéticos gerados para demonstração. Não são medições reais de satélite nem operações reais de campo.">
      <FlaskConical className="size-3" />
      {label}
    </Badge>
  );
}
