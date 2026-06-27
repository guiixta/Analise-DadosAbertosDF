"""
Conexao com o SQL Server, compartilhada pelo ETL (etl/etl_carga.py) e pelo
dashboard (app.py).

A string de conexao NUNCA fica escrita no codigo: ela e montada a partir
de variaveis de ambiente carregadas do arquivo .env (veja .env.example).
Isso evita expor usuario/senha do banco caso o repositorio seja publicado
no GitHub.
"""
import os
import urllib.parse

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

load_dotenv()


def get_engine() -> Engine:
    """Cria a engine SQLAlchemy (pyodbc) usada para falar com o SQL Server."""
    server = os.environ["DB_SERVER"]          # ex: localhost,1433
    database = os.environ["DB_NAME"]          # ex: SaudePublicaDF
    user = os.environ["DB_USER"]
    password = urllib.parse.quote_plus(os.environ["DB_PASSWORD"])
    driver = os.environ.get("DB_DRIVER", "ODBC Driver 18 for SQL Server")

    odbc_extra = "TrustServerCertificate=yes" if "18" in driver else ""
    url = (
        f"mssql+pyodbc://{user}:{password}@{server}/{database}"
        f"?driver={urllib.parse.quote_plus(driver)}"
        + (f"&{odbc_extra}" if odbc_extra else "")
    )

    # fast_executemany acelera MUITO os inserts em lote feitos pelo ETL.
    return create_engine(url, fast_executemany=True)
