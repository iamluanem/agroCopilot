"""DemoProvider: copiloto determinístico baseado em regras.

Usa as MESMAS ferramentas dos provedores LLM e monta a resposta estruturada a partir dos dados retornados.
Roda sem chave de API — ideal para gravar a demo sem custo e sem variação.
"""
import re
import unicodedata

from app.application.copilot_tools import ToolContext, run_tool
from app.core.fmt import br
from app.domain.copilot import CopilotAnswer, CopilotRequest, Fonte, TarefaProposta, ToolCall

DEMO_ALERT = "Dados de demonstração (sintéticos): não representam medições reais de satélite nem operações reais."
CAUSAL = "Melhora após intervenção indica associação, não prova causal."


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _rs(v: float | None) -> str:
    return "—" if v is None else f"R$ {br(v, 0)}"


def _dm(iso: str | None) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso else "—"


class DemoProvider:
    name = "demo"
    label = "DemoProvider (regras, sem LLM)"

    def answer(self, req: CopilotRequest, ctx: ToolContext) -> tuple[CopilotAnswer, list[ToolCall]]:
        self.calls: list[ToolCall] = []
        self.ctx = ctx
        q = _norm(req.question)
        field = self._field_from(q, req)

        if re.search(r"\b(cria|criar|crie|agend|ger[ae]|abr[ae]|abrir|program)\w*\b.*\b(vistoria|tarefa|visita)", q):
            return self._propose(field), self.calls
        if re.search(r"\b(tarefas?|pendentes?|abertas?|status da vistoria|vistorias)\b", q):
            explicit = re.search(r"\b(?:t|talhao)\s*0?(\d{1,2})\b", q)
            return self._tasks(field if explicit else None), self.calls
        if re.search(r"(evolu|depois da intervencao|apos a intervencao|recuper|resultado da intervencao|deu certo)", q):
            return self._outcomes(field), self.calls
        if re.search(r"(ja aconteceu|aconteceu antes|aconteceu aqui|historico|o que funcionou|safra passada|safra anterior|"
                     r"ano passado|memoria|antes nesse|ja teve)", q):
            return self._history(field), self.calls
        if re.search(r"(perda|prejuizo|r\$|quanto|exposicao|custo|dinheiro|valor|financeir|preco|saca|produtividade)", q):
            return self._economics(field, q), self.calls
        if re.search(r"(chuva|clima|seca|veranico|temperatura|calor)", q):
            return self._weather(), self.calls
        if re.search(r"compar", q):
            return self._compare(), self.calls
        if re.search(r"(por que|porque|pq|explica|motivo|causa|vermelho|amarelo|critico|o que (esta|ta) acontecendo)", q) \
                and field:
            return self._why(field), self.calls
        return self._summary(fallback=not re.search(r"(atencao|priori|hoje|quais|resumo|situacao|geral|urgente)", q)), self.calls

    # ------------------------------------------------------------------ helpers
    def _tool(self, name: str, **args) -> dict:
        self.calls.append(ToolCall(name=name, args=args))
        return run_tool(self.ctx, name, args)

    def _field_from(self, q: str, req: CopilotRequest) -> str | None:
        m = re.search(r"\b(?:t|talhao)\s*0?(\d{1,2})\b", q)
        if m:
            return f"T{int(m.group(1)):02d}"
        if req.field_id:
            f = next((x for x in self.ctx.farm.fields if x.id == req.field_id), None)
            if f:
                return f.code
        for h in reversed(req.history):
            m = re.search(r"\b(?:t|talhao)\s*0?(\d{1,2})\b", _norm(str(h.get("content", ""))))
            if m:
                return f"T{int(m.group(1)):02d}"
        if re.search(r"(aqui|nesse talhao|neste talhao|essa area|nessa area)", q):
            return self._top_field()
        return None

    def _top_field(self) -> str | None:
        s = self._tool("get_farm_summary")
        top = next((p for p in s["prioridades"] if p["exposicao_min"]), None)
        return top["talhao"] if top else None

    # ------------------------------------------------------------------ intents
    def _summary(self, fallback: bool = False) -> CopilotAnswer:
        s = self._tool("get_farm_summary")
        zones = [p for p in s["prioridades"] if p["exposicao_min"]]
        ev = [f"{br(s['pct_por_nivel']['verde'], 1)}% da área saudável, {br(s['pct_por_nivel']['amarelo'], 1)}% em atenção "
              f"e {br(s['pct_por_nivel']['vermelho'], 1)}% crítica em {_dm(s['data_referencia'])} (DAS {s['das']}, {s['estadio']})."]
        for p in zones:
            ev.append(f"#{p['rank']} {p['talhao']}: {br(p['area_critica_ha'], 1)} ha críticos e {br(p['area_atencao_ha'], 1)} ha "
                      f"em atenção; hipótese principal {p['hipotese_principal'].lower()} (confiança {p['confianca_hipotese']}); "
                      f"exposição estimada {_rs(p['exposicao_min'])}–{_rs(p['exposicao_max'])}.")
        ok = [p["talhao"] for p in s["prioridades"] if not p["exposicao_min"]]
        if ok:
            ev.append(f"{', '.join(ok)} sem zona relevante em anomalia.")
        if zones:
            top = zones[0]
            resumo = (f"{len(zones)} talhão(ões) precisam de atenção. Priorize o {top['talhao']}: maior exposição estimada "
                      f"({_rs(top['exposicao_min'])}–{_rs(top['exposicao_max'])}) em estádio sensível.")
            prox = f"Agendar vistoria no {top['talhao']} antes de decidir intervenção. Posso montar a tarefa."
        else:
            resumo, prox = "Nenhum talhão com zona relevante em anomalia nesta data.", "Manter monitoramento nas próximas cenas."
        if fallback:
            resumo = "Ainda não sei responder isso com os dados do app. Aqui está a situação atual da fazenda. " + resumo
        return CopilotAnswer(
            resumo=resumo, evidencias=ev, confianca="moderada",
            dados_faltantes=["Vistorias de campo nas zonas em anomalia"], proxima_acao=prox,
            fontes=[Fonte(tipo="avaliacao", rotulo=f"Avaliação {p['talhao']} em {_dm(s['data_referencia'])}",
                          ref=f"risk_assessment:{p['assessment_id']}") for p in zones]
            + [Fonte(tipo="observacoes", rotulo=f"Snapshot de risco de {_dm(s['data_referencia'])}")],
            alertas=[DEMO_ALERT, "Prioridade = exposição × urgência × confiança; exposição não é perda confirmada."],
        )

    def _why(self, field: str) -> CopilotAnswer:
        a = self._tool("get_field_risk", field=field)
        if "erro" in a:
            return self._error(a["erro"])
        if not a["has_zone"]:
            return CopilotAnswer(resumo=f"O {a['code']} não tem zona relevante em anomalia em {_dm(a['date'])}. {a['summary']}",
                                 evidencias=[f"NDVI médio {br(a['ndvi_mean'], 2)} vs. histórico {br(a['ndvi_baseline'], 2)}."],
                                 confianca="moderada", proxima_acao="Manter monitoramento.",
                                 fontes=[Fonte(tipo="observacoes", rotulo=f"Snapshot {_dm(a['date'])}")], alertas=[DEMO_ALERT])
        h = a["hypotheses"]
        top = h[0]
        level = {"vermelho": "crítico", "amarelo": "em atenção"}.get(a["level"], a["level"])
        ev = [a["observation"]] + top["evidence"]
        others = ", ".join(f"{x['cause'].lower()} ({x['confidence']})" for x in h[1:3])
        return CopilotAnswer(
            resumo=(f"O {a['code']} está {level} porque o NDVI caiu em relação ao histórico da própria área. A hipótese mais "
                    f"provável é {top['cause'].lower()} (confiança {top['confidence']}), mas isso ainda não é diagnóstico: "
                    f"precisa de vistoria. Alternativas menos prováveis: {others}."),
            evidencias=ev, confianca=top["confidence"], dados_faltantes=top["missing"], proxima_acao=a["next_step"],
            fontes=[Fonte(tipo="avaliacao", rotulo=f"Avaliação {a['code']} em {_dm(a['date'])}",
                          ref=f"risk_assessment:{a['assessment_id']}"),
                    Fonte(tipo="clima", rotulo="Clima diário dos últimos 30 dias")]
            + ([Fonte(tipo="memoria", rotulo=f"Vistoria safra {p['safra']}: {p['causa']}") for p in a["prior_verified"]]),
            alertas=[DEMO_ALERT, "Índice de satélite direciona a vistoria; não confirma a causa."],
        )

    def _economics(self, field: str | None, q: str) -> CopilotAnswer:
        field = field or self._top_field()
        price = re.search(r"(?:saca|preco)[^\d]{0,15}(\d{2,3}(?:[.,]\d+)?)", q) or re.search(r"r\$\s*(\d{2,3}(?:[.,]\d+)?)", q)
        args = {"field": field}
        if price:
            args["preco_saca_rs"] = float(price.group(1).replace(",", "."))
        e = self._tool("estimate_economics", **args)
        if "erro" in e or "mensagem" in e:
            return self._error(e.get("erro") or e["mensagem"])
        p = e["premissas"]
        sim = f" (simulação com saca a {_rs(p['preco_saca_rs'])})" if e["simulacao"] else ""
        return CopilotAnswer(
            resumo=(f"Exposição estimada no {e['talhao']}{sim}: {_rs(e['exposicao_min'])} a {_rs(e['exposicao_max'])}. "
                    "É uma faixa de risco sobre a produção da área afetada — não é perda confirmada."),
            evidencias=[f"Área afetada {br(e['area_afetada_ha'], 1)} ha = {br(p['area_critica_ha'], 1)} ha críticos + 50% de "
                        f"{br(p['area_atencao_ha'], 1)} ha em atenção.",
                        f"Valor bruto da área: {br(e['area_afetada_ha'], 1)} ha × {br(p['produtividade_esperada_sc_ha'], 0)} sc/ha × "
                        f"{_rs(p['preco_saca_rs'])}/sc = {_rs(e['valor_bruto_area'])}.",
                        f"Faixa de perda considerada: {br(p['perda_min_pct'], 0)}% a {br(p['perda_max_pct'], 0)}%.",
                        f"Custo de vistoria {_rs(e['custo_vistoria'])}; intervenção estimada {_rs(e['custo_intervencao_estimado'])}."],
            confianca="baixa" if e["simulacao"] else "moderada",
            dados_faltantes=["Causa confirmada em vistoria (define se a perda é reversível)",
                             "Produtividade realizada na colheita para calibrar a faixa de perda"],
            proxima_acao=(f"Vistoriar a zona: custo de {_rs(e['custo_vistoria'])} frente a uma exposição de até "
                          f"{_rs(e['exposicao_max'])}."),
            fontes=[Fonte(tipo="economia", rotulo=f"Modelo econômico — {e['talhao']}", ref=f"risk_assessment:{e['assessment_id']}"),
                    Fonte(tipo="configuracao", rotulo="Premissas econômicas (Configurações)")],
            alertas=[DEMO_ALERT, "Estimativa com premissas editáveis; não representa perda nem economia realizada."],
        )

    def _history(self, field: str | None) -> CopilotAnswer:
        field = field or self._top_field()
        m = self._tool("get_memory", field=field)
        o = self._tool("get_intervention_outcomes", field=field)
        if "erro" in m:
            return self._error(m["erro"])
        relevant = [e for e in m["eventos"] if e["type"] in ("anomalia", "vistoria", "intervencao", "resultado", "nota")]
        done = [i for i in o["intervencoes"] if i["resultado"]]
        if not relevant:
            return CopilotAnswer(resumo=f"Não há registro de anomalia, vistoria ou intervenção anterior no {m['talhao']}.",
                                 confianca="alta", proxima_acao="Registrar a vistoria atual para começar a memória do talhão.",
                                 dados_faltantes=["Histórico operacional anterior ao uso do app"],
                                 fontes=[Fonte(tipo="memoria", rotulo=f"Memória do {m['talhao']}")], alertas=[DEMO_ALERT])
        ev = [f"{_dm(e['date'])} — {e['title']}: {e['summary']}" for e in sorted(relevant, key=lambda e: e["date"])]
        if done:
            i = done[0]
            r = i["resultado"]
            resumo = (f"Sim. Na safra anterior o {m['talhao']} teve anomalia semelhante; a vistoria confirmou a causa e foi feita "
                      f"a intervenção \"{i['acao_aprovada'].split(' no ')[0].lower()}\" (custo {_rs(i['custo_realizado'])}). "
                      f"O NDVI do setor foi de {br(r['antes'], 2)} para {br(r['depois'], 2)}, ganho líquido de "
                      f"{br(r['delta_liquido_vs_comparacao'], 2)} vs. a área de comparação — melhora parcial, com ressalvas.")
            missing = ["Confirmar em vistoria se a causa atual é a mesma da safra anterior"]
            prox = "Vistoriar priorizando o que funcionou antes (emissores e lâmina do pivô), sem assumir a mesma causa."
            ev.append(f"Limitações do resultado anterior: {r['limitacoes']}")
            conf = r["confianca"]
        else:
            resumo = f"Há registros anteriores no {m['talhao']}, mas nenhum resultado de intervenção medido."
            missing, prox, conf = ["Medição de resultado das intervenções anteriores"], "Revisar a memória do talhão.", "baixa"
        return CopilotAnswer(
            resumo=resumo, evidencias=ev, confianca=conf, dados_faltantes=missing, proxima_acao=prox,
            fontes=[Fonte(tipo="memoria", rotulo=f"{e['title']} ({_dm(e['date'])})", ref=f"memory_event:{e['id']}") for e in relevant]
            + [Fonte(tipo="resultado", rotulo=f"Resultado da intervenção #{i['id']}", ref=f"intervention:{i['id']}") for i in done],
            alertas=[DEMO_ALERT, CAUSAL],
        )

    def _outcomes(self, field: str | None) -> CopilotAnswer:
        field = field or self._top_field()
        o = self._tool("get_intervention_outcomes", field=field)
        if "erro" in o:
            return self._error(o["erro"])
        done = [i for i in o["intervencoes"] if i["resultado"]]
        if not done:
            return CopilotAnswer(resumo=f"Não há intervenção com resultado medido no {o['talhao']}.", confianca="alta",
                                 proxima_acao="Após executar uma intervenção, registrar e simular/medir as observações seguintes.",
                                 dados_faltantes=["Intervenção registrada e observações pós-intervenção"],
                                 fontes=[Fonte(tipo="resultado", rotulo=f"Intervenções do {o['talhao']}")], alertas=[DEMO_ALERT])
        i = done[0]
        r = i["resultado"]
        return CopilotAnswer(
            resumo=(f"Após a intervenção de {_dm(i['executada_em'])} no {o['talhao']}, o NDVI do setor passou de {br(r['antes'], 2)} "
                    f"para {br(r['depois'], 2)}; descontada a área de comparação, ganho líquido de {br(r['delta_liquido_vs_comparacao'], 2)}."),
            evidencias=[f"Método: {r['metodo']}", f"Comparação: {r['area_comparacao']}",
                        f"Área de comparação: {br(r['comparacao_antes'], 2)} → {br(r['comparacao_depois'], 2)}."],
            confianca=r["confianca"], dados_faltantes=[r["limitacoes"]],
            proxima_acao="Usar este resultado como referência, não como garantia, para a decisão atual.",
            fontes=[Fonte(tipo="resultado", rotulo=f"Resultado da intervenção #{i['id']}", ref=f"intervention:{i['id']}")],
            alertas=[DEMO_ALERT, CAUSAL],
        )

    def _weather(self) -> CopilotAnswer:
        w = self._tool("get_weather", days=30)
        return CopilotAnswer(
            resumo=(f"Nos últimos 30 dias choveu {br(w['chuva_total_mm'], 0)} mm, com {w['maior_sequencia_sem_chuva_dias']} dias "
                    f"seguidos sem chuva ({_dm(w['seca_inicio'])}–{_dm(w['seca_fim'])})."),
            evidencias=[f"Máxima média no período seco: {br(w['tmax_media_no_periodo_seco'] or 0, 1)} °C.",
                        f"Chuva nos últimos 21 dias: {br(w['chuva_ultimos_21d_mm'], 0)} mm."],
            confianca="alta", dados_faltantes=["Umidade do solo medida em campo"],
            proxima_acao="Cruzar o período seco com as zonas em anomalia (pergunte: por que o T04 está vermelho?).",
            fontes=[Fonte(tipo="clima", rotulo="Clima diário (sintético)")], alertas=[DEMO_ALERT],
        )

    def _compare(self) -> CopilotAnswer:
        c = self._tool("compare_fields")
        rows = sorted(c["talhoes"], key=lambda x: (x["ndvi_medio"] or 0) - (x["ndvi_historico"] or 0))
        ev = [f"{t['talhao']}: NDVI {br(t['ndvi_medio'], 2)} vs. histórico {br(t['ndvi_historico'], 2)} "
              f"({br(t['area_critica_ha'], 1)} ha críticos, {br(t['area_atencao_ha'], 1)} ha em atenção)." for t in rows]
        return CopilotAnswer(resumo=f"O {rows[0]['talhao']} tem o maior desvio negativo em relação ao próprio histórico.",
                             evidencias=ev, confianca="alta", proxima_acao=f"Ver detalhes do {rows[0]['talhao']}.",
                             fontes=[Fonte(tipo="observacoes", rotulo=f"Snapshot de {_dm(c['data'])}")], alertas=[DEMO_ALERT])

    def _tasks(self, field: str | None) -> CopilotAnswer:
        t = self._tool("list_tasks", **({"field": field} if field else {}))
        ev = [f"#{x['id']} {x['talhao']} — {x['titulo']} · {x['status']}" + (
            f" · causa verificada: {x['vistoria']['causa_verificada']}" if x["vistoria"] else "") for x in t["tarefas"]]
        return CopilotAnswer(
            resumo=(f"{t['abertas']} tarefa(s) aberta(s) de {len(t['tarefas'])} registrada(s)"
                    + (f" no {field}." if field else " na fazenda.")),
            evidencias=ev or ["Nenhuma tarefa registrada."], confianca="alta",
            proxima_acao="Criar vistoria para a zona prioritária." if t["abertas"] == 0 else "Acompanhar as tarefas abertas.",
            fontes=[Fonte(tipo="tarefa", rotulo=f"Tarefa #{x['id']}", ref=f"task:{x['id']}") for x in t["tarefas"]],
            alertas=[DEMO_ALERT])

    def _propose(self, field: str | None) -> CopilotAnswer:
        field = field or self._top_field()
        p = self._tool("propose_inspection", field=field)
        if "erro" in p or "mensagem" in p:
            return self._error(p.get("erro") or p["mensagem"])
        t = TarefaProposta(**p["tarefa_proposta"])
        return CopilotAnswer(
            resumo=f"Montei uma proposta de vistoria para o {t.field_code}. Revise e confirme para criar a tarefa.",
            evidencias=[t.instructions], confianca="moderada",
            dados_faltantes=["Confirmação do usuário (a tarefa ainda não foi gravada)"],
            proxima_acao="Confirmar a tarefa abaixo.", tarefa_proposta=t,
            fontes=[Fonte(tipo="avaliacao", rotulo=f"Avaliação {t.field_code}", ref=f"risk_assessment:{t.assessment_id}")],
            alertas=[DEMO_ALERT])

    def _error(self, msg: str) -> CopilotAnswer:
        return CopilotAnswer(resumo=msg, confianca="baixa", proxima_acao="Reformule citando o talhão (ex.: T04).",
                             alertas=[DEMO_ALERT])
