---
marp: true
theme: default
paginate: true
---

# Como usar este arquivo

Este arquivo serve **dois** propositos ao mesmo tempo:

1. **Prompt pronto para uma IA gerar os slides visuais.** Copie o conteudo
   a partir de `# Slide 1` ate o final e cole em uma dessas ferramentas:
   - [Gamma.app](https://gamma.app) (cole o texto e peca "gerar apresentacao a partir deste outline")
   - [Tome.app](https://tome.app)
   - Canva (Magic Design / Apresentacoes com IA)
   - Microsoft Copilot / Designer (se tiver PowerPoint 365 com Copilot)
   - Ou cole direto no ChatGPT/Claude pedindo: *"Gere um arquivo .pptx com
     um slide para cada secao '# Slide N' abaixo, mantendo os bullets."*

2. **Slides prontos via Marp** (se preferir gerar localmente, sem depender
   de IA): este arquivo ja esta formatado para o [Marp](https://marp.app/),
   uma ferramenta que transforma Markdown em slides. Cada `---` separa um
   slide. Para exportar:
   ```bash
   npx @marp-team/marp-cli APRESENTACAO.md --pptx -o apresentacao.pptx
   # ou para PDF:
   npx @marp-team/marp-cli APRESENTACAO.md --pdf -o apresentacao.pdf
   ```
   (precisa de Node.js instalado; o `npx` baixa o Marp na hora, nao precisa
   instalar nada permanente).

A apresentacao tem 9 slides, pensada para caber nos **5 minutos** exigidos
pelo enunciado (≈30s por slide). Adapte o texto para a fala de quem for
apresentar — os bullets aqui sao o roteiro, nao um texto para ler na integra.

---

# Slide 1

## Pipeline de Dados de Saude Publica (DF)
### Atendimentos e Consultas - SIA/DATASUS

**ADS-5 - Trabalho Final A2** | Analise de Dados com Python e SQL-Server
Prof. Ms. Gessivaldo Costa

**Equipe-01:** Baroni, Kesia Vital, Marcus Paulo, Nickolas Taylor, Pedro Lucas, Guilherme Pessoa

---

# Slide 2

## Objetivo

Construir um pipeline completo de dados, simulando um ambiente real de
Engenharia/Ciencia de Dados:

```
CSV (Portal de Dados Abertos do DF)
        │
        ▼
ETL em Python (pandas, em lotes/chunks)
        │
        ▼
SQL Server (modelo estrela: fato + dimensoes)
        │
        ▼
Dashboard web (Dash/Plotly) com KPIs, filtros e atualizacao "em tempo real"
```

---

# Slide 3

## Fase 1 - Extracao

- Fonte: [dados.df.gov.br](https://www.dados.df.gov.br/dataset/atendimentos-e-consultas)
  dataset **"Atendimentos e Consultas"** (SIA/DATASUS)
- Equipe-01 ficou com os dados de **2017** (Janeiro, Fevereiro e Marco)
- 3 arquivos `.csv`, **553.667 linhas** no total
- Encoding original em **Latin-1** (ISO-8859-1), nao UTF-8 - primeiro
  problema de integridade que tivemos que identificar e tratar

---

# Slide 4

## Fase 2 - Armazenamento (Modelo Estrela)

- `sql/schema.sql`: `CREATE DATABASE`, tabelas, chaves primarias/estrangeiras
- 1 tabela fato + 3 dimensoes:
  - `fato_atendimento` (quantidade por mes/unidade/procedimento/carater)
  - `dim_estabelecimento`, `dim_procedimento`, `dim_carater_atendimento`
- Uma **view** (`vw_atendimentos_dashboard`) ja entrega os dados
  "desnormalizados" prontos para o Python consultar sem repetir `JOIN`s

*(Mostrar o diagrama do README.md aqui, ou um print do Database Diagram do SSMS)*

---

# Slide 5

## Fase 3 - ETL em Python (pandas)

- `etl/etl_carga.py` le cada CSV **em pedacos** (`chunksize=50.000`) -
  nunca carrega o arquivo inteiro de uma vez na memoria
- Limpeza feita no pandas:
  - `"ano_mes" → data` (primeiro dia do mes)
  - Separa o **codigo CNES** do **nome da unidade** (regex)
  - Remove espacos em branco, trata nulos
- Carga no SQL Server com `SQLAlchemy` + `pyodbc`, credenciais via `.env`
  (nunca expostas no codigo)

---

# Slide 6

## Fase 4 - Dashboard (Dash/Plotly)

- **KPIs:** total de atendimentos, taxa ambulatorial vs. emergencia
- **Grafico temporal:** evolucao mensal por categoria de atendimento
- **Filtros:** unidade de saude e especialidade (multi-selecao)
- **"Tempo real":** toda mudanca de filtro refaz a consulta no SQL Server;
  alem disso, um `dcc.Interval` repete a consulta a cada 30 segundos

*(Aqui e a hora de mostrar a tela do dashboard rodando, ou um print)*

---

# Slide 7

## Seguranca e boas praticas aplicadas

- Senha do banco **nunca** no codigo - variaveis de ambiente (`.env`,
  fora do Git)
- Filtros do usuario vao para o SQL via `bindparam` (parametrizado),
  evitando SQL Injection
- Agregacoes (`SUM`/`GROUP BY`) feitas **no SQL Server**, nao no Pandas -
  o Python so recebe o que vai ser exibido

---

# Slide 8

## Desafios reais que enfrentamos

- CSV em Latin-1 (nao UTF-8) → leitura com encoding errado
- Limite de **2100 parametros por instrucao** do SQL Server → ajuste no
  tamanho do lote de insercao
- Configuracao do **SQL Server local** (TCP/IP desabilitado por padrao,
  autenticacao mista) para o Python conseguir conectar
- Caracteres especiais (`#`) na senha do `.env` sendo cortados pelo
  parser de variaveis de ambiente

*(Esse slide mostra que o grupo realmente debugou um ambiente real - vale
pontos de "simular um ambiente real de Engenharia de Dados")*

---

# Slide 9

## Conclusao

- Pipeline completo: **extracao → SQL Server → dashboard web**, do jeito
  que um pipeline de dados real funciona
- Codigo, script SQL, README e `.env.example` no repositorio GitHub
- Repositorio: `<colar o link do GitHub aqui>`

**Perguntas?**
