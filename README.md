# AgroCopilot

**Copiloto operacional da fazenda — do alerta à prova de resultado.**

Mapas de NDVI já são commodity. O diferencial do AgroCopilot é o ciclo fechado:

> **Detectar → Priorizar (R$) → Recomendar → Tarefa → Vistoriar → Intervir → Medir → Lembrar**

O índice de satélite é um **sinal que direciona a vistoria**, nunca um diagnóstico. A plataforma separa observação,
hipótese (com confiança) e achado verificado em campo, e constrói uma memória auditável do que funcionou em cada talhão.

> ⚠️ **Dados de demonstração.** A Fazenda Santa Aurora, seus limites, NDVI/NDRE, clima e histórico operacional são
> **sintéticos e determinísticos**. Não representam medições reais de satélite nem operações reais de campo.
> Todo registro sintético tem `is_synthetic = true` e é sinalizado na interface.

![Visão Geral — prioridades por exposição em R$](docs/screenshots/fase2-visao-geral.jpg)

## Status

| Fase | Escopo | Status |
|---|---|---|
| 1 · Fundação | Docker Compose, PostGIS, migrações, seed, tela **Mapa** com talhões e células por risco | ✅ |
| 2 · Inteligência | Hipóteses com evidência e dado faltante, exposição em R$, priorização, telas **Visão Geral** e **Talhão** | ✅ |
| 3 · Copiloto | Chat com cards estruturados, 10 ferramentas sobre dados reais, `DemoProvider` + Claude/OpenAI, vistoria com confirmação | ✅ |
| 4 · Loop operacional | **Tarefas** (execução mobile com foto e rascunho offline), verificação do agrônomo, intervenção, simulação pós-intervenção, **Resultados**, memória | ✅ |
| 5 · Polimento | **Configurações** editáveis com recálculo, reinício da demo, **Sentinel-2 real** no mapa, navegação mobile | ✅ |

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

Testes (atenção: os testes de integração executam `demo/reset` e apagam o que foi criado na demonstração):
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
    UI[Visão Geral · Mapa · Talhões<br/>Copiloto · Tarefas · Resultados · Configurações]
  end
  subgraph api["backend · FastAPI"]
    R[api/routers] --> A[application<br/>risco · inteligência · copiloto · operação]
    A --> D[domain<br/>risco · hipóteses · economia · contrato do copiloto]
    A --> I[infrastructure<br/>SQLAlchemy/PostGIS · LLM providers · seed]
    T[copilot_tools] --> A
  end
  LLM[(Claude / OpenAI<br/>opcional)]
  S2[(Earth Search STAC<br/>Sentinel-2 L2A)]
  DB[(PostgreSQL 16 + PostGIS)]
  M[(volume media<br/>fotos · camadas S2)]
  UI -->|REST/JSON| R
  I --> DB
  I -.tool calling.-> LLM
  SC[scripts/fetch_sentinel.py] --> S2
  SC --> M
  R --> M
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

### Hipóteses e economia (Fase 2)

Para cada talhão em atenção/crítico, a **zona** (células amarelas + vermelhas) é materializada em `risk_assessments`
com hipóteses e estimativa econômica — o mesmo registro que tarefas e copiloto vão referenciar.

- **Hipóteses por regras** (`domain/hypotheses.py`): deficiência hídrica, pragas/doenças, nutricional e falha de estande,
  pontuadas por contexto — sequência de dias sem chuva, textura do solo, padrão espacial (setor contíguo, faixa linear,
  manchas), início da anomalia no ciclo, recorrência e vistorias anteriores. Cada uma lista **evidências** (inclusive
  contra) e o **dado que falta**. Sem vistoria, nenhuma passa de confiança *moderada*.
- **Exposição** (`domain/economics.py`): `área afetada × sc/ha × R$/sc × faixa de perda`, com área afetada = crítica +
  50% da atenção. Mostrada como faixa, com premissas visíveis. Nunca apresentada como perda ou economia realizada.
- **Prioridade** = exposição média × urgência (estádio fenológico + tendência) × peso da confiança.

### Copiloto (Fase 3)

Página **Copiloto** e gaveta no **Mapa** (com o talhão selecionado como contexto). Toda resposta segue o schema
`CopilotAnswer` (Pydantic): `resumo`, `evidencias`, `confianca`, `dados_faltantes`, `proxima_acao`, `fontes`,
`alertas` e, opcionalmente, `tarefa_proposta` — que só vira tarefa quando o usuário confirma.

| Provedor | Quando é usado |
|---|---|
| `DemoProvider` | Padrão sem chave. Regras determinísticas sobre as **mesmas ferramentas** — ideal para gravar a demo |
| Claude | `ANTHROPIC_API_KEY` definida (modelo em `ANTHROPIC_MODEL`) |
| OpenAI | `OPENAI_API_KEY` definida (modelo em `OPENAI_MODEL`) |

`LLM_PROVIDER=auto|demo|anthropic|openai` força a escolha. Se o LLM falhar, a resposta cai para o modo demo com aviso.
O LLM só acessa dados via ferramentas (`get_farm_summary`, `get_field_risk`, `get_memory`, `estimate_economics`,
`get_intervention_outcomes`, `propose_inspection`…) e termina chamando `responder`, validado contra o schema.

Para usar Claude: coloque a chave no `.env` (`ANTHROPIC_API_KEY=...`) e rode `docker compose up -d api`.

### Loop operacional (Fase 4)

`pendente → atribuída → em andamento → vistoria concluída → verificada (agrônomo) → intervenção → resultado`

- A vistoria registra achados, **causa verificada**, até 6 fotos (redimensionadas no aparelho) e fica em rascunho
  no `localStorage` enquanto é preenchida.
- Intervenção só é aceita após verificação do agrônomo; ação com produto químico exige confirmar o receituário.
- **Simular observações pós-intervenção (demo):** gera 3 cenas sintéticas (5, 10 e 15 dias depois), marcadas como
  `simulacao_pos_intervencao`, e mede o resultado por diferença-em-diferenças contra o restante do talhão.
- Cada passo vira evento na memória do talhão; o copiloto passa a responder sobre o novo resultado.
- `POST /api/demo/reset` (ou `docker compose exec api python -c "..."`) remove tudo que foi criado na demonstração.

## Roteiro do vídeo (60–90 s)

1. **Visão Geral** → T04 é a prioridade #1 com exposição em R$.
2. **Mapa** → células coloridas, troca de datas, opacidade.
3. Clique numa célula vermelha do T04 → hipóteses, confiança, dado faltante, premissas econômicas.
4. **Copiloto** (gaveta) → "Por que o Talhão 04 está vermelho?"
5. → "Isso já aconteceu aqui? O que funcionou?"
6. Painel do talhão → **Criar vistoria para esta zona**.
7. Celular (`/tarefas/<id>`) → iniciar, descrever, causa = deficiência hídrica, foto, concluir.
8. Verificar como agrônomo → registrar intervenção com custo.
9. **Simular observações pós-intervenção** → relatório de **Resultados** (antes/depois, método, limitações).
10. **Talhões → T04** → memória com o ciclo novo completo.

Para regravar: `curl -X POST localhost:8000/api/demo/reset` (PowerShell: `Invoke-RestMethod -Method Post localhost:8000/api/demo/reset`).

### Cenário demo

Fazenda Santa Aurora, Sorriso-MT, soja, ~1.191 ha, 5 talhões, safras 2023/24, 2024/25 e 2025/26 (atual).
Data de referência: 09/01/2026 (DAS 95).

- **T04 (pivô central):** queda de NDVI no setor sudoeste (~38 ha críticos) após 14 dias sem chuva.
  Na safra 2024/25 o mesmo setor teve anomalia semelhante — a vistoria confirmou deficiência hídrica (emissores
  entupidos), a intervenção foi registrada e o resultado medido com área de comparação.
- **T03:** faixa com estande irregular (atenção).
- **T01, T02, T05:** saudáveis, com variação espacial natural.

Mapa base: Esri World Imagery (sem chave). Limites dos talhões são sintéticos e não correspondem a uma propriedade real.

### Configurações e Sentinel-2 (Fase 5)

- **Configurações:** premissas econômicas, limiares de risco e peso do histórico, provedor do copiloto e
  **Reiniciar demo**. Avaliações são versionadas pelas premissas: mudar um valor gera nova versão sem quebrar tarefas e
  resultados já criados.
- **Sentinel-2 real:** `docker compose exec api python scripts/fetch_sentinel.py` busca no Earth Search a cena com menos
  nuvem dos últimos 120 dias sobre a fazenda, aplica scale/offset e a máscara SCL (nuvem, sombra, cirrus), calcula
  NDVI (B08/B04) e NDRE (B8A/B05) e gera camadas em EPSG:4326. O mapa ganha a opção **Sentinel-2 real** com data,
  % de nuvem e pixels válidos. Os limites dos talhões continuam sintéticos — a camada demonstra o pipeline de dado real.
  Opções: `--start AAAA-MM-DD --end AAAA-MM-DD --max-cloud 10 --bbox W S E N`.

## Fora do escopo (roadmap)

Detecção automática de limites de talhão · georreferenciamento manual de JPEG/PNG · sincronização offline ·
WhatsApp/voz · multi-organização e autenticação · imagens de drone · fila assíncrona (Celery/Redis).
