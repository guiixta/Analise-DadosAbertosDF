"""
ETL - carga dos dados de Atendimentos e Consultas (SIA/DATASUS - DF)
para o SQL Server.

Equipe-01: dados de 2017 (Janeiro, Fevereiro e Marco) baixados do Portal
de Dados Abertos do DF -> arquivos data/SIA012017.csv, SIA022017.csv,
SIA032017.csv.

Como o enunciado pede para NAO carregar o CSV inteiro de uma vez no
Pandas quando o volume e grande, este script le cada arquivo em pedacos
(chunks) com pandas.read_csv(..., chunksize=...) e grava cada pedaco no
banco antes de ler o proximo, mantendo o uso de memoria baixo.

Uso:
    python etl/etl_carga.py
"""
import glob
import os
import re
import sys

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_engine  # noqa: E402

CHUNK_SIZE = 50_000
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ARQUIVO_PADRAO = os.path.join(DATA_DIR, "SIA*.csv")

# Os arquivos do Portal de Dados Abertos do DF vem com acentuacao em
# ISO-8859-1 (Latin-1), e nao em UTF-8.
ENCODING_ORIGEM = "latin-1"

PADRAO_CNES = re.compile(r"^(\d{7})\s+(.*)$")

# Tabela de carater de atendimento e relativamente estatica no SIA/DATASUS,
# por isso e cadastrada uma unica vez no inicio da carga (upsert simples).
# categoria resume os 7 codigos originais em apenas 2 grupos, usados no KPI
# "taxa de emergencia vs. ambulatorial" do dashboard: somente "Eletivo" e
# tratado como atendimento programado (Ambulatorial); urgencia, acidentes e
# registros sem classificacao contam como Emergencia.
CARATERES_PADRAO = [
    ("01", "Eletivo", "Ambulatorial"),
    ("02", "Urgência", "Emergencia"),
    ("03", "Acidente no local trabalho ou a serviço da empresa", "Emergencia"),
    ("04", "Acidente no trajeto para o trabalho", "Emergencia"),
    ("05", "Outros tipo de acidente de trânsito", "Emergencia"),
    ("06", "Outros tipos lesões/envenenamentos por agentes químicos/físicos", "Emergencia"),
    ("99", "Informação inexistente  (bpa-c)", "Emergencia"),
]


def carregar_caracteres(engine, cache):
    """Garante que dim_carater_atendimento esta populada e devolve um
    dicionario {cod_carater_atendimento: carater_id}."""
    with engine.begin() as conn:
        existentes = pd.read_sql("SELECT cod_carater_atendimento FROM dim_carater_atendimento", conn)
        codigos_existentes = set(existentes["cod_carater_atendimento"])

        novos = [c for c in CARATERES_PADRAO if c[0] not in codigos_existentes]
        if novos:
            pd.DataFrame(novos, columns=["cod_carater_atendimento", "carater_atendimento", "categoria"]).to_sql(
                "dim_carater_atendimento", conn, if_exists="append", index=False
            )

        atualizado = pd.read_sql(
            "SELECT carater_id, cod_carater_atendimento FROM dim_carater_atendimento", conn
        )
    cache.update(dict(zip(atualizado["cod_carater_atendimento"], atualizado["carater_id"])))
    return cache


# Nome da coluna de chave primaria (IDENTITY) de cada tabela de dimensao.
COLUNA_ID = {
    "dim_estabelecimento": "estabelecimento_id",
    "dim_procedimento": "procedimento_id",
}


def upsert_dimensao(conn, tabela, df_novos, coluna_chave, colunas, cache):
    """Insere no banco apenas as linhas de df_novos cuja chave ainda nao
    esta em cache, e atualiza o cache {chave: id} com os novos ids."""
    chaves_novas = set(df_novos[coluna_chave]) - set(cache.keys())
    if chaves_novas:
        a_inserir = df_novos[df_novos[coluna_chave].isin(chaves_novas)].drop_duplicates(subset=[coluna_chave])
        a_inserir[colunas].to_sql(tabela, conn, if_exists="append", index=False)

        id_coluna = COLUNA_ID[tabela]
        atualizado = pd.read_sql(f"SELECT {id_coluna}, {coluna_chave} FROM {tabela}", conn)
        cache.update(dict(zip(atualizado[coluna_chave], atualizado[id_coluna])))
    return cache


def limpar_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Aplica a limpeza/transformacao em um pedaco (chunk) do CSV."""
    # ano_mes vem como string "201701" -> guardamos como data (1o dia do mes).
    chunk["competencia"] = pd.to_datetime(chunk["ano_mes"], format="%Y%m")

    # "quantidade" vem com espacos de preenchimento, ex: "         18".
    chunk["quantidade"] = chunk["quantidade"].str.strip().astype(int)

    # estabelecimento_cnes vem como "0010499 HRT Hospital Regional de Taguatinga"
    # -> separa o codigo CNES (7 digitos) do nome da unidade.
    extraido = chunk["estabelecimento_cnes"].str.extract(PADRAO_CNES)
    chunk["cnes_codigo"] = extraido[0]
    chunk["nome"] = extraido[1]  # nome da coluna ja igual ao de dim_estabelecimento

    # Os textos chegam truncados/zoados se a leitura nao usar latin-1;
    # aqui apenas garantimos que nao sobrou espaco em branco nas pontas.
    for coluna in ["complexidade", "grupo", "procedimento", "cod_carater_atendimento", "cod_forma_organizacao"]:
        chunk[coluna] = chunk[coluna].str.strip()

    return chunk.dropna(subset=["cnes_codigo", "quantidade"])


def carregar_arquivo(caminho_csv, engine, cache_estab, cache_proc, cache_carater):
    print(f"\n>> Processando {os.path.basename(caminho_csv)}")
    total_linhas = 0

    
    # Lista com a ordem exata das colunas identificadas no arquivo
    nomes_colunas = [
        "ano_mes", "estabelecimento_cnes", "complexidade", "cod_grupo", 
        "grupo", "cod_subgrupo", "cod_procedimento", "procedimento", 
        "quantidade", "cod_carater_atendimento", "carater_atendimento", 
        "cod_forma_organizacao"
    ]

    leitor = pd.read_csv(
        caminho_csv,
        encoding=ENCODING_ORIGEM,
        dtype=str,
        chunksize=CHUNK_SIZE,
        header=0,
        names=nomes_colunas
    )

    for numero_chunk, chunk in enumerate(leitor, start=1):
        chunk = limpar_chunk(chunk)

        with engine.begin() as conn:
            cache_estab = upsert_dimensao(
                conn, "dim_estabelecimento", chunk,
                coluna_chave="cnes_codigo",
                colunas=["cnes_codigo", "nome"],
                cache=cache_estab,
            )
            cache_proc = upsert_dimensao(
                conn, "dim_procedimento", chunk,
                coluna_chave="cod_procedimento",
                colunas=["cod_procedimento", "procedimento", "cod_grupo", "grupo", "cod_subgrupo"],
                cache=cache_proc,
            )

            fato = pd.DataFrame({
                "competencia": chunk["competencia"],
                "estabelecimento_id": chunk["cnes_codigo"].map(cache_estab),
                "procedimento_id": chunk["cod_procedimento"].map(cache_proc),
                "carater_id": chunk["cod_carater_atendimento"].map(cache_carater),
                "complexidade": chunk["complexidade"],
                "cod_forma_organizacao": chunk["cod_forma_organizacao"],
                "quantidade": chunk["quantidade"],
            })
            # chunksize=200: o SQL Server limita uma instrucao a 2100 parametros.
            # Com 7 colunas, 200 linhas = 1400 parametros por INSERT (seguro).
            # Valores muito maiores aqui geram o erro "COUNT field incorrect".
            fato.to_sql("fato_atendimento", conn, if_exists="append", index=False, method="multi", chunksize=200)

        total_linhas += len(chunk)
        print(f"   chunk {numero_chunk}: +{len(chunk)} linhas (acumulado: {total_linhas})")

    return cache_estab, cache_proc


def main():
    engine = get_engine()

    cache_carater = carregar_caracteres(engine, cache={})
    cache_estab, cache_proc = {}, {}

    arquivos = [
        os.path.join(DATA_DIR, "SIA012017.csv"),
        os.path.join(DATA_DIR, "SIA022017.csv"),
        os.path.join(DATA_DIR, "SIA032017.csv")
    ]

    for f in arquivos:
        if not os.path.exists(f):
            raise SystemExit(f"Arquivo obrigatório não encontrado: {f}\nVerifique se ele está na pasta data/")

    for caminho in arquivos:
        cache_estab, cache_proc = carregar_arquivo(caminho, engine, cache_estab, cache_proc, cache_carater)

    print("\nCarga finalizada com sucesso.")


if __name__ == "__main__":
    main()
