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

1. **Extracao**: arquivos `.csv` baixados manualmente do portal e colocados
   em `data/`. Integridade verificada antes da carga: separador `,` com
   campos entre aspas, sem valores nulos nas colunas usadas, e
   `estabelecimento_cnes` sempre no formato `"<7 digitos> <nome>"` (checado
   nos 553.667 registros das 3 competencias).
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

### Diagrama logico (modelo estrela)

```
                    ┌──────────────────────────┐
                    │   dim_estabelecimento     │
                    │----------------------------│
                    │ estabelecimento_id  (PK)   │
                    │ cnes_codigo         (UQ)   │
                    │ nome                       │
                    └─────────────┬──────────────┘
                                  │
                                  │ 1
┌──────────────────────────┐     │     ┌──────────────────────────┐
│   dim_procedimento        │     │     │ dim_carater_atendimento   │
│----------------------------│     │     │----------------------------│
│ procedimento_id     (PK)   │  N  │  1  │ carater_id          (PK)   │
│ cod_procedimento    (UQ)   │◄────┼────►│ cod_carater_at...   (UQ)   │
│ procedimento               │     │     │ carater_atendimento        │
│ cod_grupo / grupo          │     │     │ categoria (Ambulat./Emerg.)│
│ cod_subgrupo               │     │     └─────────────┬──────────────┘
└─────────────┬──────────────┘     │                   │ 1
              │ 1                  │                   │
              │                    ▼ N                 │ N
              └──────────►┌──────────────────────────┐◄┘
                           │     fato_atendimento      │
                           │----------------------------│
                           │ atendimento_id      (PK)   │
                           │ competencia                │
                           │ estabelecimento_id  (FK)   │
                           │ procedimento_id     (FK)   │
                           │ carater_id          (FK)   │
                           │ complexidade               │
                           │ cod_forma_organizacao      │
                           │ quantidade                 │
                           └────────────────────────────┘
```

`fato_atendimento` e a tabela fato (1 linha por mes/unidade/procedimento/
carater); as tres `dim_*` sao as dimensoes. A view `vw_atendimentos_dashboard`
(criada no mesmo `schema.sql`) junta as quatro tabelas para o Python nunca
precisar fazer `JOIN` na aplicacao.

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

> **Atencao a senhas com `#`:** o `python-dotenv` trata `#` como inicio de
> comentario em valores sem aspas. Se a senha do seu SQL Server tiver `#`
> (ou outro caractere especial), coloque-a entre aspas duplas no `.env`,
> senão o valor lido fica truncado e a conexao falha por "senha errada":
> ```env
> DB_PASSWORD="sua-senha#comAlgumEspecial"
> ```

### 3. Habilitar o SQL Server para aceitar conexoes do Python (TCP/IP)

Por padrao, instalacoes locais do SQL Server (Express/Developer) aceitam
conexoes do SSMS via Named Pipes/Shared Memory, mas **nao** tem o protocolo
TCP/IP habilitado - e e isso que o `pyodbc`/`SQLAlchemy` usam. Sem esse
passo, o Python falha com `Login timeout expired` ou
`target machine actively refused it`, mesmo com o SSMS funcionando normalmente.

1. Abra o **SQL Server Configuration Manager** (não tem icone fixo - aperte
   `Win + R` e rode, por exemplo, `SQLServerManager17.msc`; se nao existir,
   tente outros numeros de versao, ou liste com
   `Get-ChildItem "C:\Windows\System32\SQLServerManager*.msc"`).
2. `SQL Server Network Configuration` → `Protocols for MSSQLSERVER` → clique
   direito em **TCP/IP** → **Enable**.
3. De um duplo clique em **TCP/IP** → aba **IP Addresses** → secao **IPAll**
   → limpe `TCP Dynamic Ports` e defina `TCP Port = 1433`.
4. Reinicie o servico: `SQL Server Services` → botao direito em
   **SQL Server (MSSQLSERVER)** → **Restart** (ou
   `Restart-Service -Name MSSQLSERVER -Force` no PowerShell, como Admin).
5. Confirme que a porta abriu: `Test-NetConnection -ComputerName localhost -Port 1433`
   deve retornar `TcpTestSucceeded : True`.

Se for conectar usando um login SQL (`sa` + senha, como no `.env.example`)
em vez de autenticacao do Windows, garanta tambem:

6. No SSMS: clique direito no servidor (raiz do Object Explorer) →
   **Properties** → **Security** → marque **"SQL Server and Windows
   Authentication mode"** → reinicie o servico de novo.
7. `Security → Logins → sa` → **Properties**: defina a senha igual ao
   `.env` (aba **General**) e confirme `Login = Enabled` (aba **Status**).

### 4. Criar o banco e as tabelas

Execute o script `sql/schema.sql` no SQL Server (via SSMS, Azure Data
Studio ou `sqlcmd`):

```bash
sqlcmd -S localhost,1433 -U sa -P 'sua-senha-aqui' -i sql/schema.sql
```

### 5. Baixar os dados (se a pasta `data/` estiver vazia)

Baixe os CSVs de Janeiro/Fevereiro/Marco de 2017 em
https://www.dados.df.gov.br/dataset/atendimentos-e-consultas e salve em
`data/` com os nomes `SIA012017.csv`, `SIA022017.csv`, `SIA032017.csv`
(os CSVs nao vao para o GitHub por serem grandes - veja `.gitignore`).

### 6. Rodar o ETL (carga dos dados)

```bash
python etl/etl_carga.py
```

O script imprime o progresso por lote (`chunk`) de cada arquivo. Ao final,
o total de linhas carregadas deve ser igual ao numero de linhas dos CSVs
(174.870 + 187.635 + 191.162 = 553.667 no caso da Equipe-01).

### 7. Rodar o dashboard

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

## Solucao de problemas (erros reais que enfrentamos)

| Erro | Causa | Solucao |
|---|---|---|
| `Login timeout expired` / `target machine actively refused it` | TCP/IP desabilitado no SQL Server local | Passo 3 acima (Configuration Manager) |
| Conexao falha mesmo com a senha certa | `.env` tem `#` ou outro caractere especial na senha, sem aspas | Colocar a senha entre aspas duplas no `.env` |
| `python` no PowerShell nao mostra nada e nao faz nada | Python nao instalado de verdade (so existe o "alias" da Microsoft Store) | Instalar o Python em https://python.org (marcar "Add to PATH") |
| `time data "ano_mes" doesn't match format` | `pd.read_csv` com `header=None` tratando a linha de cabecalho do CSV como dado | Usar `header=0` (pula a 1a linha) junto com `names=...` |
| `COUNT field incorrect or syntax error` no `to_sql` | INSERT multi-linha excedeu o limite de 2100 parametros do SQL Server (linhas x colunas) | Reduzir o `chunksize` do `to_sql` (usamos 200, com 7 colunas = 1400 parametros) |
| Tabelas existem mas `SELECT` retorna 0 linhas | Conferir se o `USE NomeDoBanco;` foi executado antes do `SELECT` no SSMS, e se o ETL realmente terminou sem erro | Sempre checar a saida do `etl_carga.py` ate a linha "Carga finalizada com sucesso." |
