# AgroCopilot

**Copiloto operacional da fazenda — do alerta à prova de resultado.**

Mapas de NDVI já são commodity. O diferencial do AgroCopilot é o ciclo fechado:

> **Detectar → Priorizar (R$) → Recomendar → Tarefa → Vistoriar → Intervir → Medir → Lembrar**

O índice de satélite é um **sinal que direciona a vistoria**, nunca um diagnóstico. A plataforma separa observação,
hipótese (com confiança) e achado verificado em campo, e constrói uma memória auditável do que funcionou em cada talhão.

> ⚠️ **Dados de demonstração.** A Fazenda Santa Aurora, seus limites, NDVI/NDRE, clima e histórico operacional são
> **sintéticos e determinísticos**. Não representam medições reais de satélite nem operações reais de campo.
> Todo registro sintético tem `is_synthetic = true` e é sinalizado na interface.

![Talhão 04 — setor sudoeste do pivô em vermelho](docs/screenshots/fase1-talhao04.jpg)

## Status

| Fase | Escopo | Status |
|---|---|---|
| 1 · Fundação | Docker Compose, PostGIS, migrações, seed, tela **Mapa** com talhões e células por risco | ✅ |
| 2 · Inteligência | Hipóteses, modelo econômico (R$), painel da célula, tela Talhão | ⏳ |
| 3 · Copiloto | Abstração de LLM, `DemoProvider`, ferramentas, cards estruturados | ⏳ |
| 4 · Loop operacional | Tarefas, vistoria mobile, intervenção, relatório de resultado, memória | ⏳ |
| 5 · Polimento | Visão Geral, Configurações, script Sentinel-2, testes, UI para gravação | ⏳ |

## Como rodar

Pré-requisito: Docker Desktop.

**macOS / Linux**
```bash
cp .env.example .env
docker compose up --build
```

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
docker compose up --build
```

Na primeira subida a API aplica as migrações e o seed (~20 s). Depois abra:

- App: http://localhost:3000
- API (OpenAPI): http://localhost:8000/docs

Recriar o seed do zero:
```bash
docker compose exec api python -m app.infrastructure.seed.seed --reset
```

Testes:
```bash
docker compose exec api pytest -q
```

### Desenvolvimento sem Docker para API/web

```bash
docker compose up -d db
# backend
cd backend && python3.12 -m venv .venv && source .venv/bin/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://agro:agro@localhost:5433/agrocopilot  # PowerShell: $env:DATABASE_URL="..."
alembic upgrade head && python -m app.infrastructure.seed.seed
uvicorn app.api.main:app --reload
# frontend (outro terminal)
cd frontend && npm install && npm run dev
```

## Arquitetura

```mermaid
flowchart LR
  subgraph web["frontend · Next.js"]
    MAP[Mapa · MapLibre GL]
    PANEL[Painel do talhão/célula · Recharts]
  end
  subgraph api["backend · FastAPI"]
    R[api/routers] --> A[application<br/>casos de uso]
    A --> D[domain<br/>motor de risco puro]
    A --> I[infrastructure<br/>SQLAlchemy · GeoAlchemy2]
    S[seed determinístico] --> I
  end
  DB[(PostgreSQL 16<br/>+ PostGIS)]
  MAP -- GeoJSON + snapshot de risco --> R
  PANEL --> R
  I --> DB
```

```
backend/
  app/domain/          regras puras (motor de risco) — sem I/O, 100% testável
  app/application/     casos de uso (consultas do mapa, snapshot de risco)
  app/infrastructure/  banco (modelos, sessão) e seed do cenário demo
  app/api/             rotas FastAPI
  alembic/             migrações
frontend/
  src/components/map/  mapa, timeline de datas, legenda, painel lateral
```

### Motor de risco (Fase 1)

Para cada célula de manejo de 30 × 30 m, numa data de observação:

- `z_hist`: diferença entre o NDVI atual e a média da **própria célula no mesmo estádio (DAS)** em safras anteriores,
  descontada a variação geral da fazenda nesta safra (para não marcar a fazenda inteira em ano seco);
- `z_talhão`: desvio robusto (mediana/MAD) em relação à mediana do talhão na mesma data;
- `score = −(0,6·z_hist + 0,4·z_talhão)`. Atenção ≥ 1,5; crítico ≥ 2,5 (configurável);
- confiança: concordância entre as duas referências + existência de histórico + observações válidas recentes;
- observações com nuvem são descartadas (célula fica "sem dado").

### Cenário demo

Fazenda Santa Aurora, Sorriso-MT, soja, ~1.191 ha, 5 talhões, safras 2023/24, 2024/25 e 2025/26 (atual).
Data de referência: 09/01/2026 (DAS 95).

- **T04 (pivô central):** queda de NDVI no setor sudoeste (~38 ha críticos) após 14 dias sem chuva.
  Na safra 2024/25 o mesmo setor teve anomalia semelhante — a vistoria confirmou deficiência hídrica (emissores
  entupidos), a intervenção foi registrada e o resultado medido com área de comparação.
- **T03:** faixa com estande irregular (atenção).
- **T01, T02, T05:** saudáveis, com variação espacial natural.

Mapa base: Esri World Imagery (sem chave). Limites dos talhões são sintéticos e não correspondem a uma propriedade real.

## Fora do escopo (roadmap)

Detecção automática de limites de talhão · georreferenciamento manual de JPEG/PNG · sincronização offline ·
WhatsApp/voz · multi-organização e autenticação · imagens de drone · fila assíncrona (Celery/Redis).
