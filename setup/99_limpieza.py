# Databricks notebook source
# MAGIC %md
# MAGIC # Taller La Tinka · Limpieza
# MAGIC
# MAGIC Borra todo lo que creó `00_setup_taller`: la app, el dashboard, el espacio de Genie, el warehouse y el esquema con sus tablas.
# MAGIC El catálogo solo se borra si lo creó el setup.
# MAGIC
# MAGIC **No se puede deshacer.** Escribe `BORRAR` en el campo **confirmar** y corre el notebook.
# MAGIC Las copias del dashboard que hicieron los participantes en sus carpetas no se tocan.

# COMMAND ----------

dbutils.widgets.text("catalogo", "la_tinka_taller", "1. Catálogo")
dbutils.widgets.text("esquema", "mesa_servicio", "2. Esquema")
dbutils.widgets.text("confirmar", "", "3. Escribe BORRAR para confirmar")

# COMMAND ----------

from databricks.sdk import WorkspaceClient

CATALOGO = dbutils.widgets.get("catalogo").strip()
ESQUEMA = dbutils.widgets.get("esquema").strip()
assert dbutils.widgets.get("confirmar").strip() == "BORRAR", "Escribe BORRAR en el campo 'confirmar' para continuar."

w = WorkspaceClient()
T = f"`{CATALOGO}`.`{ESQUEMA}`"
config = {r.clave: r.valor for r in spark.sql(f"SELECT clave, valor FROM {T}.taller_config").collect()}


def intentar(texto, metodo, ruta):
    try:
        w.api_client.do(metodo, ruta)
        print(f"  ✓ {texto}")
    except Exception as e:
        print(f"  · {texto}: {e}")


if config.get("app"):
    intentar(f"App {config['app']}", "DELETE", f"/api/2.0/apps/{config['app']}")
if config.get("dashboard_id"):
    intentar("Dashboard", "DELETE", f"/api/2.0/lakeview/dashboards/{config['dashboard_id']}")
if config.get("genie_id"):
    intentar("Espacio de Genie", "DELETE", f"/api/2.0/genie/spaces/{config['genie_id']}")
if config.get("warehouse_id"):
    intentar("SQL Warehouse", "DELETE", f"/api/2.0/sql/warehouses/{config['warehouse_id']}")

spark.sql(f"DROP SCHEMA IF EXISTS {T} CASCADE")
print(f"  ✓ Esquema {CATALOGO}.{ESQUEMA}")
if config.get("catalogo_creado_por_setup") == "si":
    spark.sql(f"DROP CATALOG IF EXISTS `{CATALOGO}` CASCADE")
    print(f"  ✓ Catálogo {CATALOGO}")
