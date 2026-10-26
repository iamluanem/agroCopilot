import { FlaskConical } from "lucide-react";
import { Badge } from "./badge";

export function DemoBadge({ label = "Demo data", className }: { label?: string; className?: string }) {
  return (
    <Badge tone="demo" className={className} title="Synthetic data generated for the demo. Not real satellite measurements or real field operations.">
      <FlaskConical className="size-3" />
      {label}
    </Badge>
  );
}
