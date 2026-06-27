/* =====================================================================
   PROJETO: Pipeline de Dados de Saude Publica (DF) - SIA/DATASUS
   Equipe-01 (Baroni, Kesia Vital, Marcus Paulo, Nickolas Taylor,
              Pedro Lucas, Guilherme Pessoa) - Dados de 2017 (Jan/Fev/Mar)

   Este script cria o banco, as tabelas (modelo estrela) e a view usada
   pelo dashboard em Python. Rode-o uma unica vez, antes da carga (ETL).

   Modelo logico:
     dim_estabelecimento  -> unidades de saude (CNES)
     dim_procedimento     -> procedimentos / grupo / subgrupo
     dim_carater_atendimento -> caracter do atendimento (Eletivo/Urgencia/...)
                                 + categoria simplificada (Ambulatorial/Emergencia)
     fato_atendimento     -> 1 linha por (mes, unidade, procedimento, carater,
                              complexidade) com a quantidade de atendimentos
   ===================================================================== */

IF DB_ID(N'SaudePublicaDF') IS NULL
BEGIN
    CREATE DATABASE SaudePublicaDF;
END
GO

USE SaudePublicaDF;
GO

/* ---------------------------------------------------------------------
   Limpeza (permite rodar o script novamente do zero em ambiente de dev)
   --------------------------------------------------------------------- */
IF OBJECT_ID(N'dbo.vw_atendimentos_dashboard', N'V') IS NOT NULL
    DROP VIEW dbo.vw_atendimentos_dashboard;
GO
IF OBJECT_ID(N'dbo.fato_atendimento', N'U') IS NOT NULL
    DROP TABLE dbo.fato_atendimento;
IF OBJECT_ID(N'dbo.dim_procedimento', N'U') IS NOT NULL
    DROP TABLE dbo.dim_procedimento;
IF OBJECT_ID(N'dbo.dim_estabelecimento', N'U') IS NOT NULL
    DROP TABLE dbo.dim_estabelecimento;
IF OBJECT_ID(N'dbo.dim_carater_atendimento', N'U') IS NOT NULL
    DROP TABLE dbo.dim_carater_atendimento;
GO

/* ---------------------------------------------------------------------
   DIMENSAO: Estabelecimento de saude (codigo CNES + nome)
   --------------------------------------------------------------------- */
CREATE TABLE dbo.dim_estabelecimento (
    estabelecimento_id  INT IDENTITY(1,1) NOT NULL,
    cnes_codigo          VARCHAR(7)    NOT NULL,
    nome                  NVARCHAR(200) NOT NULL,  -- NVARCHAR: nomes com acentuacao (ex: "Brasília")
    CONSTRAINT PK_dim_estabelecimento PRIMARY KEY (estabelecimento_id),
    CONSTRAINT UQ_dim_estabelecimento_cnes UNIQUE (cnes_codigo)
);
GO

/* ---------------------------------------------------------------------
   DIMENSAO: Procedimento (inclui grupo/subgrupo do procedimento)
   --------------------------------------------------------------------- */
CREATE TABLE dbo.dim_procedimento (
    procedimento_id  INT IDENTITY(1,1) NOT NULL,
    cod_procedimento  VARCHAR(10)   NOT NULL,
    procedimento      NVARCHAR(250) NOT NULL,
    cod_grupo         VARCHAR(2)    NOT NULL,
    grupo             NVARCHAR(150) NOT NULL,
    cod_subgrupo      VARCHAR(4)    NOT NULL,
    CONSTRAINT PK_dim_procedimento PRIMARY KEY (procedimento_id),
    CONSTRAINT UQ_dim_procedimento_cod UNIQUE (cod_procedimento)
);
GO

/* ---------------------------------------------------------------------
   DIMENSAO: Carater do atendimento. "categoria" resume os 7 valores
   originais do dataset em apenas 2 grandes grupos usados no KPI do
   dashboard (taxa emergencia vs. ambulatorial).
   --------------------------------------------------------------------- */
CREATE TABLE dbo.dim_carater_atendimento (
    carater_id            INT IDENTITY(1,1) NOT NULL,
    cod_carater_atendimento VARCHAR(2)    NOT NULL,
    carater_atendimento     NVARCHAR(100) NOT NULL,
    categoria                VARCHAR(20)   NOT NULL,  -- 'Ambulatorial' | 'Emergencia'
    CONSTRAINT PK_dim_carater_atendimento PRIMARY KEY (carater_id),
    CONSTRAINT UQ_dim_carater_cod UNIQUE (cod_carater_atendimento),
    CONSTRAINT CK_dim_carater_categoria CHECK (categoria IN ('Ambulatorial', 'Emergencia'))
);
GO

/* ---------------------------------------------------------------------
   FATO: um registro por (mes, estabelecimento, procedimento, carater,
   complexidade, forma de organizacao). "quantidade" e a metrica.
   --------------------------------------------------------------------- */
CREATE TABLE dbo.fato_atendimento (
    atendimento_id        BIGINT IDENTITY(1,1) NOT NULL,
    competencia            DATE         NOT NULL,   -- primeiro dia do mes (ano_mes)
    estabelecimento_id     INT           NOT NULL,
    procedimento_id         INT           NOT NULL,
    carater_id               INT           NOT NULL,
    complexidade             NVARCHAR(30)  NOT NULL,
    cod_forma_organizacao    VARCHAR(10)   NOT NULL,
    quantidade                INT          NOT NULL,
    CONSTRAINT PK_fato_atendimento PRIMARY KEY (atendimento_id),
    CONSTRAINT FK_fato_estabelecimento FOREIGN KEY (estabelecimento_id)
        REFERENCES dbo.dim_estabelecimento (estabelecimento_id),
    CONSTRAINT FK_fato_procedimento FOREIGN KEY (procedimento_id)
        REFERENCES dbo.dim_procedimento (procedimento_id),
    CONSTRAINT FK_fato_carater FOREIGN KEY (carater_id)
        REFERENCES dbo.dim_carater_atendimento (carater_id),
    CONSTRAINT CK_fato_quantidade CHECK (quantidade >= 0)
);
GO

/* Indices para acelerar os filtros mais usados pelo dashboard */
CREATE INDEX IX_fato_competencia ON dbo.fato_atendimento (competencia);
CREATE INDEX IX_fato_estabelecimento ON dbo.fato_atendimento (estabelecimento_id);
CREATE INDEX IX_fato_carater ON dbo.fato_atendimento (carater_id);
GO

/* ---------------------------------------------------------------------
   VIEW usada pelo Python: ja entrega os dados "desnormalizados" e
   prontos para os SELECTs do dashboard, evitando repetir JOINs no
   codigo da aplicacao (e respeitando a dica de performance do
   enunciado: o Python so traz o que vai exibir).
   --------------------------------------------------------------------- */
CREATE VIEW dbo.vw_atendimentos_dashboard AS
SELECT
    f.atendimento_id,
    f.competencia,
    YEAR(f.competencia)   AS ano,
    MONTH(f.competencia)  AS mes,
    e.cnes_codigo,
    e.nome                 AS estabelecimento,
    p.cod_procedimento,
    p.procedimento,
    p.grupo                AS especialidade,
    f.complexidade,
    c.carater_atendimento,
    c.categoria             AS categoria_atendimento,
    f.quantidade
FROM dbo.fato_atendimento f
JOIN dbo.dim_estabelecimento e ON e.estabelecimento_id = f.estabelecimento_id
JOIN dbo.dim_procedimento p    ON p.procedimento_id    = f.procedimento_id
JOIN dbo.dim_carater_atendimento c ON c.carater_id     = f.carater_id;
GO
