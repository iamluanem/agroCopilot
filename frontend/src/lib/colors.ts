import type { Level } from "./types";

export const LEVEL_COLOR: Record<Level, string> = {
  verde: "#22a35a",
  amarelo: "#f2b705",
  vermelho: "#e0362c",
  sem_dado: "#94a3b8",
};

export const LEVEL_LABEL: Record<Level, string> = {
  verde: "Saudável",
  amarelo: "Atenção",
  vermelho: "Crítico",
  sem_dado: "Sem dado (nuvem)",
};

export const LEVEL_DESC: Record<Level, string> = {
  verde: "Sem anomalia significativa",
  amarelo: "Anomalia moderada — acompanhar",
  vermelho: "Anomalia alta — priorizar vistoria",
  sem_dado: "Observação descartada por nuvem",
};

// Rampa contínua para índices de vegetação (vermelho → amarelo → verde)
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
