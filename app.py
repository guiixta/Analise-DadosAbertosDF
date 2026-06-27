"""
Dashboard de Atendimentos e Consultas - Saude Publica do DF
=============================================================
Equipe-01 (Baroni, Kesia Vital, Marcus Paulo, Nickolas Taylor, Pedro Lucas,
Guilherme Pessoa) - ADS-5 / Trabalho Final A2.

Fonte dos dados: Portal de Dados Abertos do DF, dataset "Atendimentos e
Consultas" (SIA/DATASUS), competencias de Janeiro, Fevereiro e Marco/2017.

Stack: Dash + Plotly (graficos web), SQLAlchemy/pyodbc para falar com o
SQL Server. Todas as consultas usam a view dbo.vw_atendimentos_dashboard
criada em sql/schema.sql.

Como rodar: veja o README.md na raiz do projeto.
"""
import datetime

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html
from sqlalchemy import bindparam, text

from db import get_engine

engine = get_engine()

# Quantas unidades aparecem no grafico de "top unidades". E uma constante
# fixa do programa (nao vem do usuario), por isso pode entrar direto no SQL
# sem risco de injection.
TOP_N_UNIDADES = 10


# ---------------------------------------------------------------------------
# Opcoes dos filtros (dropdowns): carregadas UMA VEZ, na inicializacao do
# app, pois sao metadados (nomes de unidades/especialidades) que praticamente
# nao mudam. Os DADOS exibidos nos graficos e KPIs, por outro lado, sao
# buscados no SQL Server a cada interacao do usuario - isso e feito dentro
# do callback `atualizar_dashboard`, mais abaixo, simulando "tempo real".
# ---------------------------------------------------------------------------
def carregar_opcoes_filtro():
    estabelecimentos = pd.read_sql(
        "SELECT DISTINCT estabelecimento FROM vw_atendimentos_dashboard ORDER BY estabelecimento",
        engine,
    )["estabelecimento"].tolist()

    especialidades = pd.read_sql(
        "SELECT DISTINCT especialidade FROM vw_atendimentos_dashboard ORDER BY especialidade",
        engine,
    )["especialidade"].tolist()

    return estabelecimentos, especialidades


def _filtros_sql(unidades, especialidades):
    """Monta a clausula WHERE e os parametros de bind a partir dos filtros
    escolhidos pelo usuario. Usa bindparam(expanding=True) para o SQL Server
    receber as listas como IN (...) de forma segura (sem concatenar string
    vinda do usuario na query, o que abriria espaco para SQL Injection)."""
    condicoes = ["1 = 1"]
    params = {}
    binds = []

    if unidades:
        condicoes.append("estabelecimento IN :unidades")
        params["unidades"] = unidades
        binds.append(bindparam("unidades", expanding=True))

    if especialidades:
        condicoes.append("especialidade IN :especialidades")
        params["especialidades"] = especialidades
        binds.append(bindparam("especialidades", expanding=True))

    return " AND ".join(condicoes), params, binds


def consultar_serie_temporal(unidades, especialidades):
    """Total de atendimentos por mes (competencia) e categoria
    (Ambulatorial/Emergencia). A agregacao (SUM/GROUP BY) e feita no SQL
    Server, e nao no Pandas: assim o Python recebe apenas algumas linhas
    em vez das ~550 mil linhas da tabela fato (dica de performance)."""
    where, params, binds = _filtros_sql(unidades, especialidades)
    sql = text(
        f"""
        SELECT competencia, categoria_atendimento, SUM(quantidade) AS total
        FROM vw_atendimentos_dashboard
        WHERE {where}
        GROUP BY competencia, categoria_atendimento
        ORDER BY competencia
        """
    ).bindparams(*binds)
    return pd.read_sql(sql, engine, params=params)


def consultar_top_unidades(unidades, especialidades):
    """Unidades de saude com mais atendimentos, dentro dos filtros atuais."""
    where, params, binds = _filtros_sql(unidades, especialidades)
    sql = text(
        f"""
        SELECT TOP {TOP_N_UNIDADES} estabelecimento, SUM(quantidade) AS total
        FROM vw_atendimentos_dashboard
        WHERE {where}
        GROUP BY estabelecimento
        ORDER BY SUM(quantidade) DESC
        """
    ).bindparams(*binds)
    return pd.read_sql(sql, engine, params=params)


OPCOES_ESTABELECIMENTO, OPCOES_ESPECIALIDADE = carregar_opcoes_filtro()


# ---------------------------------------------------------------------------
# Layout (HTML da pagina)
# ---------------------------------------------------------------------------
app = Dash(__name__)
app.title = "Atendimentos e Consultas - SES/DF"

ESTILO_CARTAO = {
    "flex": 1,
    "background": "#ffffff",
    "borderRadius": "10px",
    "padding": "16px 20px",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.12)",
    "textAlign": "center",
}

app.layout = html.Div(
    style={"fontFamily": "Arial, sans-serif", "background": "#f4f6f8", "padding": "24px"},
    children=[
        html.H1("Atendimentos e Consultas - Saude Publica do DF"),
        html.P(
            "Fonte: Portal de Dados Abertos do DF - dataset SIA/DATASUS "
            "(competencias de Jan/Fev/Mar de 2017)."
        ),
        html.P(
            "Observacao sobre granularidade: o SIA/DATASUS so disponibiliza os "
            "atendimentos agregados por MES (competencia), e nao por dia/hora. "
            "Por isso o grafico de evolucao temporal abaixo mostra a serie "
            "mensal; o pipeline (ETL + banco + dashboard) esta pronto para uma "
            "granularidade diaria/horaria caso a fonte de dados disponibilize.",
            style={"fontStyle": "italic", "color": "#555"},
        ),
        # ----- Filtros -----
        html.Div(
            style={"display": "flex", "gap": "20px", "margin": "20px 0"},
            children=[
                html.Div(
                    style={"flex": 1},
                    children=[
                        html.Label("Unidade de saude"),
                        dcc.Dropdown(
                            id="filtro-unidade",
                            options=[{"label": u, "value": u} for u in OPCOES_ESTABELECIMENTO],
                            multi=True,
                            placeholder="Todas as unidades",
                        ),
                    ],
                ),
                html.Div(
                    style={"flex": 1},
                    children=[
                        html.Label("Especialidade (grupo de procedimento)"),
                        dcc.Dropdown(
                            id="filtro-especialidade",
                            options=[{"label": e, "value": e} for e in OPCOES_ESPECIALIDADE],
                            multi=True,
                            placeholder="Todas as especialidades",
                        ),
                    ],
                ),
            ],
        ),
        # ----- KPIs -----
        html.Div(id="kpis", style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),
        # ----- Graficos -----
        dcc.Graph(id="grafico-temporal"),
        dcc.Graph(id="grafico-top-unidades"),
        html.Div(id="rodape-atualizacao", style={"color": "#777", "marginTop": "12px"}),
        # Atualizacao automatica a cada 30s, alem da atualizacao disparada
        # por qualquer mudanca nos filtros - simula um dashboard "em tempo
        # real" sem precisar de WebSocket.
        dcc.Interval(id="intervalo-atualizacao", interval=30 * 1000, n_intervals=0),
    ],
)


def cartao_kpi(titulo, valor):
    return html.Div(
        style=ESTILO_CARTAO,
        children=[
            html.Div(titulo, style={"color": "#666", "fontSize": "14px"}),
            html.H2(valor, style={"margin": "6px 0 0 0"}),
        ],
    )


# ---------------------------------------------------------------------------
# Callback principal: roda sempre que o usuario muda um filtro OU quando o
# intervalo de 30s dispara. Em ambos os casos, refaz as consultas no SQL
# Server (nada fica em cache no processo Python).
# ---------------------------------------------------------------------------
@app.callback(
    Output("kpis", "children"),
    Output("grafico-temporal", "figure"),
    Output("grafico-top-unidades", "figure"),
    Output("rodape-atualizacao", "children"),
    Input("filtro-unidade", "value"),
    Input("filtro-especialidade", "value"),
    Input("intervalo-atualizacao", "n_intervals"),
)
def atualizar_dashboard(unidades, especialidades, _n_intervalos):
    unidades = unidades or []
    especialidades = especialidades or []

    serie = consultar_serie_temporal(unidades, especialidades)
    top_unidades = consultar_top_unidades(unidades, especialidades)

    total = serie["total"].sum()
    total_emergencia = serie.loc[serie["categoria_atendimento"] == "Emergencia", "total"].sum()
    total_ambulatorial = serie.loc[serie["categoria_atendimento"] == "Ambulatorial", "total"].sum()
    taxa_emergencia = (total_emergencia / total * 100) if total else 0
    taxa_ambulatorial = (total_ambulatorial / total * 100) if total else 0

    kpis = [
        cartao_kpi("Total de atendimentos", f"{total:,.0f}".replace(",", ".")),
        cartao_kpi("Taxa ambulatorial", f"{taxa_ambulatorial:.1f}%"),
        cartao_kpi("Taxa de emergencia", f"{taxa_emergencia:.1f}%"),
    ]

    fig_temporal = px.line(
        serie,
        x="competencia",
        y="total",
        color="categoria_atendimento",
        markers=True,
        labels={
            "competencia": "Mes",
            "total": "Atendimentos",
            "categoria_atendimento": "Categoria",
        },
        title="Evolucao mensal dos atendimentos (Ambulatorial vs. Emergencia)",
    )

    fig_top = px.bar(
        top_unidades.sort_values("total"),
        x="total",
        y="estabelecimento",
        orientation="h",
        labels={"total": "Atendimentos", "estabelecimento": "Unidade de saude"},
        title=f"Top {TOP_N_UNIDADES} unidades de saude por volume de atendimentos",
    )

    rodape = (
        f"Dados consultados no SQL Server em {datetime.datetime.now():%d/%m/%Y %H:%M:%S} "
        "(a query e refeita a cada filtro alterado e a cada 30s)."
    )

    return kpis, fig_temporal, fig_top, rodape


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
