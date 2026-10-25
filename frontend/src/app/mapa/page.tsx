import { Suspense } from "react";
import { MapWorkspace } from "@/components/map/map-workspace";
import { Loading } from "@/components/ui/states";

export default function MapaPage() {
  return (
    <Suspense fallback={<Loading label="Carregando mapa…" />}>
      <MapWorkspace />
    </Suspense>
  );
}
