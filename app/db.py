"""Acceso a datos del Laboratorio de IA.

La app corre con autorización de app: todas las consultas usan el service principal
de la app, no la identidad de quien está conectado.
"""

import os

import pandas as pd
from databricks import sql
from databricks.sdk.core import Config

CATALOGO = os.environ["TALLER_CATALOGO"]
ESQUEMA = os.environ["TALLER_ESQUEMA"]
MODELO = os.environ.get("TALLER_MODELO", "databricks-claude-haiku-4-5")
WAREHOUSE_ID = os.environ["DATABRICKS_WAREHOUSE_ID"]
T = f"`{CATALOGO}`.`{ESQUEMA}`"

_cfg = Config()


def lit(texto: str) -> str:
    """Literal SQL escapado. Las AI Functions exigen constantes para etiquetas y esquemas."""
    return "'" + texto.replace("\\", "\\\\").replace("'", "\\'") + "'"


def consultar(sentencia: str, parametros: dict | None = None) -> pd.DataFrame:
    # Una conexión por consulta: el conector no es thread-safe y Streamlit atiende sesiones en paralelo
    with sql.connect(server_hostname=_cfg.host, http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
                     credentials_provider=lambda: _cfg.authenticate) as conn:
        with conn.cursor() as cur:
            cur.execute(sentencia, parametros or {})
            filas = cur.fetchall()
            columnas = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(filas, columns=columnas)


def ejecutar(sentencia: str, parametros: dict | None = None) -> None:
    with sql.connect(server_hostname=_cfg.host, http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
                     credentials_provider=lambda: _cfg.authenticate) as conn:
        with conn.cursor() as cur:
            cur.execute(sentencia, parametros or {})
