import type { Level } from "./types";

export const LEVEL_COLOR: Record<Level, string> = {
  green: "#22a35a",
  yellow: "#f2b705",
  red: "#e0362c",
  no_data: "#94a3b8",
};

export const LEVEL_LABEL: Record<Level, string> = {
  green: "Healthy",
  yellow: "Watch",
  red: "Critical",
  no_data: "No data (cloud)",
};

export const LEVEL_DESC: Record<Level, string> = {
  green: "No significant anomaly",
  yellow: "Moderate anomaly — keep an eye on it",
  red: "Strong anomaly — prioritize an inspection",
  no_data: "Observation discarded due to clouds",
};

// Continuous ramp for vegetation indices (red → yellow → green)
export const INDEX_RAMP: Record<"ndvi" | "ndre", [number, string][]> = {
  ndvi: [
    [0.3, "#a50026"],
    [0.55, "#f46d43"],
    [0.7, "#fee08b"],
    [0.8, "#a6d96a"],
    [0.9, "#1a9850"],
  ],
  ndre: [
    [0.2, "#a50026"],
    [0.32, "#f46d43"],
    [0.4, "#fee08b"],
    [0.46, "#a6d96a"],
    [0.52, "#1a9850"],
  ],
};
