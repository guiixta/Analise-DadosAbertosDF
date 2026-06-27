# Pipeline de Dados de Saude Publica (DF) - Atendimentos e Consultas

Trabalho Final A2 - ADS-5 / Analise de Dados com Python e SQL-Server
(Prof. Ms. Gessivaldo Costa).

**Equipe-01:** Baroni, Kesia Vital, Marcus Paulo, Nickolas Taylor, Pedro
Lucas, Guilherme Pessoa.

**Dados utilizados:** dataset "Atendimentos e Consultas" do [Portal de
Dados Abertos do DF](https://www.dados.df.gov.br/dataset/atendimentos-e-consultas)
(SIA/DATASUS), competencias de **Janeiro, Fevereiro e Marco de 2017**
(conforme atribuido a Equipe-01).

## Visao geral do pipeline

```
CSV (dados.df.gov.br)  --->  ETL em Python (pandas)  --->  SQL Server  --->  Dashboard (Dash/Plotly)
   data/SIA*.csv             etl/etl_carga.py            sql/schema.sql        app.py
```

1. **Extracao**: arquivos `.csv` baixados manualmente do portal e colocados em `data/`.
2. **Armazenamento**: `sql/schema.sql` cria o banco `SaudePublicaDF` em modelo estrela:
   - `dim_estabelecimento` - unidades de saude (codigo CNES + nome).
   - `dim_procedimento` - procedimento + grupo/subgrupo (especialidade).
   - `dim_carater_atendimento` - carater do atendimento (Eletivo, Urgencia, etc.) e a
     `categoria` resumida usada no KPI (`Ambulatorial` vs. `Emergencia`).
   - `fato_atendimento` - quantidade de atendimentos por mes (competencia),
     estabelecimento, procedimento e carater. Chaves primarias/estrangeiras
     definidas no proprio script.
   - `vw_atendimentos_dashboard` - view que junta fato + dimensoes, usada
     pelo Python para nao precisar repetir `JOIN`s na aplicacao.
3. **ETL**: `etl/etl_carga.py` le cada CSV em pedacos (`chunksize`), limpa
   os dados (datas, espacos, separa codigo/nome da unidade) e grava no SQL
   Server.
4. **Visualizacao**: `app.py` e um dashboard Dash (Plotly) que consulta a
   view a cada interacao do usuario (filtro alterado) e a cada 30 segundos
   (`dcc.Interval`), simulando atualizacao em tempo real.

### Sobre a granularidade temporal

O dataset do SIA/DATASUS so informa o mes de competencia (`ano_mes`), e
nao a data/hora exata de cada atendimento. Por isso o grafico de "evolucao
temporal" do dashboard mostra a serie **mensal** (3 pontos: Jan/Fev/Mar
2017). O pipeline (banco + ETL + dashboard) ja esta pronto para granularidade
diaria/horaria, bastaria a fonte de dados ter essa informacao.

## Pre-requisitos

- Python 3.10+
- SQL Server (local, Docker ou Azure SQL) acessivel pela rede
- [Driver ODBC para SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
  instalado na maquina que vai rodar o Python (driver 17 ou 18)

## Como rodar

### 1. Clonar o repositorio e instalar as dependencias

```bash
git clone <url-do-repositorio>
cd gessi
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar a conexao com o banco

Copie `.env.example` para `.env` e preencha com os dados do seu SQL Server:

```bash
cp .env.example .env
```

```env
DB_SERVER=localhost,1433
DB_NAME=SaudePublicaDF
DB_USER=sa
DB_PASSWORD=sua-senha-aqui
DB_DRIVER=ODBC Driver 18 for SQL Server
```

O arquivo `.env` nunca e commitado (esta no `.gitignore`) - a senha do
banco nunca fica exposta no codigo, conforme pedido no enunciado.

### 3. Criar o banco e as tabelas

Execute o script `sql/schema.sql` no SQL Server (via SSMS, Azure Data
Studio ou `sqlcmd`):

```bash
sqlcmd -S localhost,1433 -U sa -P 'sua-senha-aqui' -i sql/schema.sql
```

### 4. Baixar os dados (se a pasta `data/` estiver vazia)

Baixe os CSVs de Janeiro/Fevereiro/Marco de 2017 em
https://www.dados.df.gov.br/dataset/atendimentos-e-consultas e salve em
`data/` com os nomes `SIA012017.csv`, `SIA022017.csv`, `SIA032017.csv`
(os CSVs nao vao para o GitHub por serem grandes - veja `.gitignore`).

### 5. Rodar o ETL (carga dos dados)

```bash
python etl/etl_carga.py
```

O script imprime o progresso por lote (`chunk`) de cada arquivo.

### 6. Rodar o dashboard

```bash
python app.py
```

Acesse http://localhost:8050 no navegador.

## Estrutura do repositorio

```
gessi/
├── app.py                 # Dashboard Dash/Plotly (KPIs, graficos, filtros)
├── db.py                  # Conexao SQLAlchemy/pyodbc compartilhada
├── etl/
│   └── etl_carga.py       # Extrai dos CSVs, limpa e carrega no SQL Server
├── sql/
│   └── schema.sql          # CREATE DATABASE/TABLE, PK/FK e a view do dashboard
├── data/                   # CSVs de origem (nao versionados)
├── .env.example             # Modelo da string de conexao
├── requirements.txt
└── README.md
```

## Requisitos do dashboard atendidos

- **KPIs**: total de atendimentos, taxa ambulatorial e taxa de emergencia.
- **Grafico temporal**: evolucao mensal dos atendimentos por categoria.
- **Filtros**: unidade de saude e especialidade (grupo de procedimento).
- **Atualizacao "tempo real"**: toda mudanca de filtro, e tambem a cada
  30 segundos, refaz a consulta no SQL Server (sem cache local).
