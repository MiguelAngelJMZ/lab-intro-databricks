# Databricks notebook source
# MAGIC %md
# MAGIC # Taller de iniciación en Databricks – La Tinka · Setup
# MAGIC
# MAGIC Este notebook deja listo **todo** lo que necesita el taller:
# MAGIC
# MAGIC | | Qué crea |
# MAGIC |---|---|
# MAGIC | Datos | Catálogo, esquema y tablas sintéticas de una mesa de servicio de TI |
# MAGIC | Cómputo | Un SQL Warehouse serverless `Taller La Tinka` |
# MAGIC | Lab 1 | Espacio de Genie **Mesa de servicio** |
# MAGIC | Lab 2 | Dashboard **Mesa de servicio – Seguimiento** publicado |
# MAGIC | Lab 3 | App **Laboratorio de IA** |
# MAGIC | Permisos | Acceso del grupo de participantes a todo lo anterior |
# MAGIC
# MAGIC ### Cómo usarlo
# MAGIC 1. Llena los campos de arriba (**catalogo**, **esquema**, **grupo_participantes**).
# MAGIC 2. Conecta el notebook a **Serverless** y haz clic en **Run all**.
# MAGIC 3. Al terminar, Genie, el dashboard y la app quedan en la carpeta **Taller La Tinka** de tu usuario.
# MAGIC
# MAGIC Puedes correrlo varias veces: no duplica nada, solo actualiza. **Ojo:** cada corrida vacía el marcador del reto de la app.
# MAGIC
# MAGIC **Requisitos:** que quien lo corra sea administrador del workspace (o tenga permiso para crear catálogos, warehouses y apps), y que el grupo de participantes ya exista en el workspace.

# COMMAND ----------

dbutils.widgets.text("catalogo", "la_tinka_taller", "1. Catálogo")
dbutils.widgets.text("esquema", "mesa_servicio", "2. Esquema")
dbutils.widgets.text("grupo_participantes", "taller_iniciacion", "3. Grupo de participantes")
dbutils.widgets.text("fecha_taller", "2026-11-26", "4. Fecha del taller (opcional)")

# COMMAND ----------

import os, sys, json, time
from datetime import date

sys.path.append(os.path.abspath("recursos"))
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ImportFormat

import datos, consultas, genie, dashboard

CATALOGO = dbutils.widgets.get("catalogo").strip()
ESQUEMA = dbutils.widgets.get("esquema").strip()
GRUPO = dbutils.widgets.get("grupo_participantes").strip()
FECHA_TALLER = date.fromisoformat(dbutils.widgets.get("fecha_taller").strip() or "2026-11-26")

NOMBRE_WAREHOUSE = "Taller La Tinka"
NOMBRE_GENIE = "Mesa de servicio"
NOMBRE_DASHBOARD = "Mesa de servicio – Seguimiento"
NOMBRE_APP = "laboratorio-ia-tinka"
# Modelos candidatos para ai_query, en orden de preferencia (se usa el primero disponible)
MODELOS = ["databricks-claude-haiku-4-5", "databricks-claude-sonnet-4-5", "databricks-gpt-oss-120b",
           "databricks-meta-llama-3-3-70b-instruct", "databricks-gpt-oss-20b"]

assert CATALOGO and ESQUEMA and GRUPO, "Llena catalogo, esquema y grupo_participantes."

w = WorkspaceClient()
YO = w.current_user.me().user_name
HOST = w.config.host.rstrip("/")
T = f"`{CATALOGO}`.`{ESQUEMA}`"
CARPETA = f"/Workspace/Users/{YO}/Taller La Tinka"
RAIZ_REPO = os.path.dirname(os.path.abspath("."))  # carpeta que contiene setup/ y app/


def api(metodo, ruta, cuerpo=None):
    return w.api_client.do(metodo, ruta, body=cuerpo)


def paso(n, texto):
    print(f"\n━━━ Paso {n}: {texto}")


def ok(texto):
    print(f"  ✓ {texto}")


class ErrorSetup(Exception):
    """Error con un mensaje en español que explica qué hacer."""

# COMMAND ----------

# MAGIC %md ## Paso 1 – Validaciones previas

# COMMAND ----------

paso(1, "Validaciones previas")
grupos = list(w.groups.list(filter=f'displayName eq "{GRUPO}"', attributes="id,displayName"))
if not grupos:
    raise ErrorSetup(
        f"No encuentro el grupo '{GRUPO}' en este workspace. Pide a un administrador de la cuenta que cree el grupo "
        f"(a nivel de cuenta), agregue a los participantes y lo asigne a este workspace. Después vuelve a correr el notebook.")
ok(f"Grupo '{GRUPO}' encontrado")

metastore = spark.sql("SELECT current_metastore()").first()[0]
ok(f"Unity Catalog activo (metastore {metastore.split(':')[-1]})")
ok(f"Corriendo como {YO}")

# COMMAND ----------

# MAGIC %md ## Paso 2 – Catálogo y esquema

# COMMAND ----------

paso(2, "Catálogo y esquema")
existia_catalogo = CATALOGO in [r.catalog for r in spark.sql("SHOW CATALOGS").collect()]
if not existia_catalogo:
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS `{CATALOGO}` COMMENT 'Taller de iniciación en Databricks – La Tinka'")
    except Exception as e:
        raise ErrorSetup(
            f"No pude crear el catálogo '{CATALOGO}'. Si tu metastore no tiene almacenamiento por defecto, crea el catálogo "
            f"desde Catalog Explorer (eligiendo una ubicación de almacenamiento) y vuelve a correr el notebook.\nDetalle: {e}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {T} COMMENT 'Mesa de servicio de TI (datos sintéticos) para el taller'")
ok(f"{CATALOGO}.{ESQUEMA} listo")

spark.sql(f"CREATE TABLE IF NOT EXISTS {T}.taller_config (clave STRING, valor STRING) "
          "COMMENT 'Identificadores de los recursos creados por el setup (lo usa el notebook de limpieza)'")


def config_leer(clave):
    fila = spark.sql(f"SELECT valor FROM {T}.taller_config WHERE clave = '{clave}'").first()
    return fila[0] if fila else None


def config_guardar(clave, valor):
    spark.sql(f"MERGE INTO {T}.taller_config t USING (SELECT '{clave}' AS clave, '{valor}' AS valor) s "
              "ON t.clave = s.clave WHEN MATCHED THEN UPDATE SET valor = s.valor WHEN NOT MATCHED THEN INSERT *")


if not existia_catalogo:
    config_guardar("catalogo_creado_por_setup", "si")
config_guardar("fecha_taller", FECHA_TALLER.isoformat())

# COMMAND ----------

# MAGIC %md ## Paso 3 – SQL Warehouse serverless

# COMMAND ----------

paso(3, "SQL Warehouse serverless")
wh = next((x for x in api("GET", "/api/2.0/sql/warehouses").get("warehouses", []) if x["name"] == NOMBRE_WAREHOUSE), None)
if wh is None:
    try:
        wh = api("POST", "/api/2.0/sql/warehouses", {
            "name": NOMBRE_WAREHOUSE, "cluster_size": "2X-Small", "min_num_clusters": 1, "max_num_clusters": 2,
            "auto_stop_mins": 15, "enable_serverless_compute": True, "warehouse_type": "PRO",
            "tags": {"custom_tags": [{"key": "proyecto", "value": "taller-la-tinka"}]},
        })
    except Exception as e:
        raise ErrorSetup(f"No pude crear el SQL Warehouse serverless. Verifica que serverless esté habilitado en el workspace.\nDetalle: {e}")
WAREHOUSE_ID = wh["id"]
config_guardar("warehouse_id", WAREHOUSE_ID)
ok(f"Warehouse '{NOMBRE_WAREHOUSE}' ({WAREHOUSE_ID}), 2X-Small, 1–2 clusters")


def sql_warehouse(sentencia, timeout_s=600):
    """Ejecuta SQL en el warehouse del taller (las AI Functions solo corren en warehouses serverless/pro)."""
    r = api("POST", "/api/2.0/sql/statements", {"warehouse_id": WAREHOUSE_ID, "statement": sentencia,
                                                 "wait_timeout": "50s", "on_wait_timeout": "CONTINUE"})
    inicio = time.time()
    while r["status"]["state"] in ("PENDING", "RUNNING"):
        if time.time() - inicio > timeout_s:
            raise ErrorSetup(f"La consulta tardó más de {timeout_s}s")
        time.sleep(3)
        r = api("GET", f"/api/2.0/sql/statements/{r['statement_id']}")
    if r["status"]["state"] != "SUCCEEDED":
        raise ErrorSetup(r["status"].get("error", {}).get("message", str(r["status"])))
    return r.get("result", {}).get("data_array", [])

# COMMAND ----------

# MAGIC %md ## Paso 4 – Funciones de IA y modelo para `ai_query`

# COMMAND ----------

paso(4, "Funciones de IA")
try:
    fila = sql_warehouse("SELECT ai_classify('No me llegó el pago del premio', '{\"pagos\": \"dinero o premios\", \"acceso\": \"login\"}'), "
                         "ai_extract('Por la app me cobraron S/ 40', '{\"canal\": {\"type\": \"string\"}}'), "
                         "ai_analyze_sentiment('Pésimo servicio')")[0]
except Exception as e:
    raise ErrorSetup(
        "Las funciones de IA no respondieron. Revisa que estén habilitadas en el workspace (Settings → Previews / "
        f"Partner-powered AI features) y que la región las soporte.\nDetalle: {e}")
ok(f"ai_classify, ai_extract y ai_analyze_sentiment funcionan ({fila[2]})")

MODELO = None
for m in MODELOS:
    try:
        if api("GET", f"/api/2.0/serving-endpoints/{m}").get("state", {}).get("ready") == "READY":
            sql_warehouse(f"SELECT ai_query('{m}', 'Responde solo: ok')")
            MODELO = m
            break
    except Exception:
        continue
if MODELO is None:
    raise ErrorSetup(f"Ningún modelo para ai_query está disponible. Probé: {', '.join(MODELOS)}. "
                     "Habilita al menos uno en Serving → Foundation Model APIs.")
config_guardar("modelo", MODELO)
ok(f"ai_query usará el modelo {MODELO}")

# COMMAND ----------

# MAGIC %md ## Paso 5 – Datos sintéticos

# COMMAND ----------

paso(5, "Datos sintéticos")
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType, DateType, DoubleType

tablas = datos.generar(FECHA_TALLER)

ESQUEMAS = {
    "equipos": (
        "Equipos de la mesa de servicio, con su gerente y área.",
        [("equipo", StringType(), "Nombre del equipo resolutor"),
         ("gerente", StringType(), "Gerente responsable del equipo"),
         ("area", StringType(), "Área de la empresa a la que pertenece el equipo")]),
    "incidencias": (
        "Tickets de la mesa de servicio de TI: reclamos de jugadores, agentes y fallas internas.",
        [("id_incidencia", StringType(), "Identificador del ticket (INC-00001)"),
         ("fecha_apertura", TimestampType(), "Fecha y hora en que se abrió el ticket"),
         ("fecha_cierre", TimestampType(), "Fecha y hora de cierre; vacía si sigue abierto"),
         ("prioridad", StringType(), "P1 (urgente) a P4 (baja)"),
         ("categoria", StringType(), "Tipo de problema"),
         ("equipo", StringType(), "Equipo que atiende el ticket"),
         ("estatus", StringType(), "Abierta, En progreso o Cerrada"),
         ("sla_horas", IntegerType(), "Horas comprometidas para resolver según la prioridad"),
         ("descripcion", StringType(), "Texto libre del reclamo")]),
    "encuestas_satisfaccion": (
        "Encuesta que responde el usuario al cerrarse su incidencia.",
        [("id_incidencia", StringType(), "Ticket evaluado (une con incidencias)"),
         ("calificacion", IntegerType(), "Calificación de 1 (muy mala) a 5 (excelente)"),
         ("comentario", StringType(), "Comentario libre del usuario"),
         ("fecha_encuesta", DateType(), "Fecha en que se respondió la encuesta")]),
    "proyectos": (
        "Proyectos del área de TI con su avance y fecha compromiso.",
        [("id_proyecto", StringType(), "Identificador del proyecto"),
         ("nombre", StringType(), "Nombre del proyecto"),
         ("responsable", StringType(), "Líder del proyecto"),
         ("fecha_inicio", DateType(), "Fecha de inicio"),
         ("fecha_compromiso", DateType(), "Fecha comprometida de entrega"),
         ("pct_avance", IntegerType(), "Porcentaje de avance (0 a 100)"),
         ("estatus", StringType(), "En curso, En riesgo, En pausa o Completado")]),
    "reto_clasificacion_gold": (
        "Respuestas correctas del reto de clasificación (solo la app las lee).",
        [("id_reto", IntegerType(), ""), ("descripcion", StringType(), ""), ("categoria_real", StringType(), "")]),
    "reto_extraccion_gold": (
        "Respuestas correctas del reto de extracción (solo la app las lee).",
        [("id_reto", IntegerType(), ""), ("texto", StringType(), ""), ("canal", StringType(), ""),
         ("juego", StringType(), ""), ("monto_reclamado", DoubleType(), "")]),
    "reto_respuesta_casos": (
        "Comentarios negativos para la ronda 3 del reto.",
        [("id_reto", IntegerType(), ""), ("comentario", StringType(), "")]),
}

for nombre, (comentario_tabla, columnas) in ESQUEMAS.items():
    esquema_spark = StructType([StructField(c, tipo, True) for c, tipo, _ in columnas])
    filas = [tuple(r[c] for c, _, _ in columnas) for r in tablas[nombre]]
    (spark.createDataFrame(filas, esquema_spark).write.mode("overwrite")
     .option("overwriteSchema", "true").saveAsTable(f"{T}.{nombre}"))
    spark.sql(f"COMMENT ON TABLE {T}.{nombre} IS '{comentario_tabla}'")
    for c, _, desc in columnas:
        if desc:
            spark.sql(f"ALTER TABLE {T}.{nombre} ALTER COLUMN {c} COMMENT '{desc}'")
    ok(f"{nombre}: {len(filas):,} filas")

spark.sql(consultas.vista_incidencias_sla(CATALOGO, ESQUEMA))
ok("vista incidencias_sla")

# COMMAND ----------

# MAGIC %md ## Paso 6 – Tablas del reto y resultados de IA precalculados

# COMMAND ----------

paso(6, "Tablas del reto (Lab 3)")
spark.sql(f"""CREATE OR REPLACE TABLE {T}.reto_intentos (
  id_intento STRING, email STRING, ronda INT, ts TIMESTAMP, propuesta STRING, resultado STRING, puntaje DOUBLE)
  COMMENT 'Envíos de los participantes al reto de la app (se vacía en cada corrida del setup)'""")
spark.sql(f"""CREATE OR REPLACE TABLE {T}.reto_votos (email STRING, id_intento STRING, ts TIMESTAMP)
  COMMENT 'Votos de la ronda 3 del reto'""")
ok("reto_intentos y reto_votos vacías")

# Las pestañas Sentimiento y Resumir son iguales para todos: se calculan una vez aquí
sql_warehouse(f"""CREATE OR REPLACE TABLE {T}.encuestas_sentimiento
COMMENT 'Encuestas con el sentimiento calculado por ai_analyze_sentiment (precalculado para la app)' AS
WITH s AS (SELECT comentario, ai_analyze_sentiment(comentario) AS sentimiento
           FROM (SELECT DISTINCT comentario FROM {T}.encuestas_satisfaccion))
SELECT e.id_incidencia, i.equipo, i.categoria, e.fecha_encuesta, e.calificacion, e.comentario, s.sentimiento
FROM {T}.encuestas_satisfaccion e
JOIN {T}.incidencias i ON e.id_incidencia = i.id_incidencia
JOIN s ON e.comentario = s.comentario""")
ok("encuestas_sentimiento (ai_analyze_sentiment)")

sql_warehouse(f"""CREATE OR REPLACE TABLE {T}.resumen_negativos_semana
COMMENT 'Resumen semanal de comentarios negativos (ai_summarize + ai_translate, precalculado para la app)' AS
WITH semanas AS (
  SELECT date_trunc('WEEK', e.fecha_encuesta) AS semana, COUNT(*) AS comentarios,
         concat_ws(' | ', collect_list(concat(i.equipo, ': ', e.comentario))) AS texto
  FROM {T}.encuestas_satisfaccion e JOIN {T}.incidencias i ON e.id_incidencia = i.id_incidencia
  WHERE e.calificacion <= 2 AND e.fecha_encuesta >= date_sub(DATE'{FECHA_TALLER}', 84) AND e.fecha_encuesta < DATE'{FECHA_TALLER}'
  GROUP BY 1)
SELECT semana, comentarios, resumen, ai_translate(resumen, 'en') AS resumen_en
FROM (SELECT semana, comentarios, ai_translate(ai_summarize(texto, 60), 'es') AS resumen FROM semanas)""")
ok("resumen_negativos_semana (ai_summarize, ai_translate)")

# COMMAND ----------

# MAGIC %md ## Paso 7 – Espacio de Genie "Mesa de servicio" (Lab 1)

# COMMAND ----------

paso(7, "Espacio de Genie")
w.workspace.mkdirs(CARPETA)
espacio = genie.construir(CATALOGO, ESQUEMA, FECHA_TALLER)
GENIE_ID = config_leer("genie_id")
descripcion_genie = genie.DESCRIPCION
try:
    if GENIE_ID:
        api("PATCH", f"/api/2.0/genie/spaces/{GENIE_ID}", {"serialized_space": espacio, "warehouse_id": WAREHOUSE_ID,
                                                             "title": NOMBRE_GENIE, "description": descripcion_genie})
        ok("Espacio actualizado")
    else:
        raise LookupError
except Exception:
    GENIE_ID = api("POST", "/api/2.0/genie/spaces", {"serialized_space": espacio, "warehouse_id": WAREHOUSE_ID,
                                                      "title": NOMBRE_GENIE, "description": descripcion_genie,
                                                      "parent_path": CARPETA})["space_id"]
    ok("Espacio creado")
config_guardar("genie_id", GENIE_ID)

# COMMAND ----------

# MAGIC %md ## Paso 8 – Dashboard "Mesa de servicio – Seguimiento" (Lab 2)

# COMMAND ----------

paso(8, "Dashboard")
cuerpo = {"display_name": NOMBRE_DASHBOARD, "warehouse_id": WAREHOUSE_ID,
          "serialized_dashboard": dashboard.construir(CATALOGO, ESQUEMA, FECHA_TALLER, GENIE_ID)}
DASHBOARD_ID = config_leer("dashboard_id")
try:
    if DASHBOARD_ID and api("GET", f"/api/2.0/lakeview/dashboards/{DASHBOARD_ID}").get("lifecycle_state") == "ACTIVE":
        api("PATCH", f"/api/2.0/lakeview/dashboards/{DASHBOARD_ID}", cuerpo)
        ok("Dashboard actualizado")
    else:
        raise LookupError
except Exception:
    DASHBOARD_ID = api("POST", "/api/2.0/lakeview/dashboards", {**cuerpo, "parent_path": CARPETA})["dashboard_id"]
    ok("Dashboard creado")
config_guardar("dashboard_id", DASHBOARD_ID)
# embed_credentials=False: cada persona ve el tablero con sus propios permisos
api("POST", f"/api/2.0/lakeview/dashboards/{DASHBOARD_ID}/published", {"warehouse_id": WAREHOUSE_ID, "embed_credentials": False})
ok("Dashboard publicado")

# COMMAND ----------

# MAGIC %md ## Paso 9 – App "Laboratorio de IA" (Lab 3)

# COMMAND ----------

paso(9, "App Laboratorio de IA")
# 1) Copia el código de la app a la carpeta del taller y genera app.yaml con el catálogo y esquema elegidos
origen = os.path.join(RAIZ_REPO, "app")
destino = f"{CARPETA}/app_laboratorio_ia"
for raiz, _, archivos in os.walk(origen):
    for archivo in archivos:
        if archivo == "app.yaml" or "__pycache__" in raiz:
            continue
        rel = os.path.relpath(os.path.join(raiz, archivo), origen)
        w.workspace.mkdirs(os.path.dirname(f"{destino}/{rel}"))
        with open(os.path.join(raiz, archivo), "rb") as fh:
            w.workspace.upload(f"{destino}/{rel}", fh.read(), format=ImportFormat.AUTO, overwrite=True)
app_yaml = f"""command: ["streamlit", "run", "app.py"]
env:
  - name: DATABRICKS_WAREHOUSE_ID
    valueFrom: sql-warehouse
  - name: TALLER_MODELO
    valueFrom: serving-endpoint
  - name: TALLER_CATALOGO
    value: "{CATALOGO}"
  - name: TALLER_ESQUEMA
    value: "{ESQUEMA}"
  - name: TALLER_FECHA
    value: "{FECHA_TALLER.isoformat()}"
"""
w.workspace.upload(f"{destino}/app.yaml", app_yaml.encode(), format=ImportFormat.AUTO, overwrite=True)
ok(f"Código copiado a {destino}")

# 2) Crea la app (o actualiza sus recursos) y espera a que su cómputo esté activo
recursos = [{"name": "sql-warehouse", "sql_warehouse": {"id": WAREHOUSE_ID, "permission": "CAN_USE"}},
            {"name": "serving-endpoint", "serving_endpoint": {"name": MODELO, "permission": "CAN_QUERY"}}]
try:
    app = api("GET", f"/api/2.0/apps/{NOMBRE_APP}")
    app = api("PATCH", f"/api/2.0/apps/{NOMBRE_APP}", {"name": NOMBRE_APP, "resources": recursos})
except Exception:
    app = api("POST", "/api/2.0/apps", {"name": NOMBRE_APP, "resources": recursos,
                                         "description": "Laboratorio de IA del taller La Tinka: AI Functions sin escribir SQL"})
    ok("App creada")
config_guardar("app", NOMBRE_APP)

inicio = time.time()
while True:
    app = api("GET", f"/api/2.0/apps/{NOMBRE_APP}")
    estado = app.get("compute_status", {}).get("state")
    if estado == "ACTIVE":
        break
    if estado in ("STOPPED", "ERROR"):
        api("POST", f"/api/2.0/apps/{NOMBRE_APP}/start")
    if time.time() - inicio > 900:
        raise ErrorSetup("El cómputo de la app no se activó en 15 minutos. Revisa la app en Compute → Apps.")
    time.sleep(10)
ok("Cómputo de la app activo")

# 3) Permisos del service principal de la app (solo lo que necesita)
SP = app["service_principal_client_id"]
for sentencia in [
    f"GRANT USE CATALOG ON CATALOG `{CATALOGO}` TO `{SP}`",
    f"GRANT USE SCHEMA ON SCHEMA {T} TO `{SP}`",
    *[f"GRANT SELECT ON TABLE {T}.{t} TO `{SP}`" for t in
      ["incidencias", "encuestas_satisfaccion", "encuestas_sentimiento", "resumen_negativos_semana",
       "reto_clasificacion_gold", "reto_extraccion_gold", "reto_respuesta_casos"]],
    *[f"GRANT SELECT, MODIFY ON TABLE {T}.{t} TO `{SP}`" for t in ["reto_intentos", "reto_votos"]],
]:
    spark.sql(sentencia)
ok("Permisos del service principal de la app")

# 4) Despliegue
dep = api("POST", f"/api/2.0/apps/{NOMBRE_APP}/deployments", {"source_code_path": destino, "mode": "SNAPSHOT"})
inicio = time.time()
while dep.get("status", {}).get("state") in (None, "IN_PROGRESS"):
    if time.time() - inicio > 900:
        raise ErrorSetup("El despliegue de la app tardó más de 15 minutos.")
    time.sleep(10)
    dep = api("GET", f"/api/2.0/apps/{NOMBRE_APP}/deployments/{dep['deployment_id']}")
if dep["status"]["state"] != "SUCCEEDED":
    raise ErrorSetup(f"El despliegue de la app falló: {dep['status'].get('message')}. Revisa los logs en Compute → Apps → {NOMBRE_APP}.")
APP_URL = app.get("url")
ok(f"App desplegada: {APP_URL}")

# COMMAND ----------

# MAGIC %md ## Paso 10 – Permisos del grupo de participantes

# COMMAND ----------

paso(10, f"Permisos del grupo '{GRUPO}'")
# Datos: solo las tablas del taller. Las respuestas del reto (reto_*) quedan ocultas para los participantes.
for sentencia in [
    f"GRANT USE CATALOG ON CATALOG `{CATALOGO}` TO `{GRUPO}`",
    f"GRANT USE SCHEMA ON SCHEMA {T} TO `{GRUPO}`",
    *[f"GRANT SELECT ON TABLE {T}.{t} TO `{GRUPO}`" for t in
      ["equipos", "incidencias", "encuestas_satisfaccion", "proyectos", "incidencias_sla", "encuestas_sentimiento"]],
]:
    spark.sql(sentencia)
ok("Datos: USE CATALOG, USE SCHEMA y SELECT sobre las tablas del taller")


def dar_permiso(tipo, id_objeto, nivel):
    api("PATCH", f"/api/2.0/permissions/{tipo}/{id_objeto}",
        {"access_control_list": [{"group_name": GRUPO, "permission_level": nivel}]})


dar_permiso("sql/warehouses", WAREHOUSE_ID, "CAN_USE")
ok("Warehouse: CAN USE")
dar_permiso("genie", GENIE_ID, "CAN_RUN")
ok("Genie: CAN RUN")
dar_permiso("dashboards", DASHBOARD_ID, "CAN_RUN")
ok("Dashboard: CAN RUN (ver y clonar)")
dar_permiso("apps", NOMBRE_APP, "CAN_USE")
ok("App: CAN USE")
