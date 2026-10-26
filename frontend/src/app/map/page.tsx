import { Suspense } from "react";
import { MapWorkspace } from "@/components/map/map-workspace";
import { Loading } from "@/components/ui/states";

export default function MapPage() {
  return (
    <Suspense fallback={<Loading label="Loading map…" />}>
      <MapWorkspace />
    </Suspense>
  );
}
