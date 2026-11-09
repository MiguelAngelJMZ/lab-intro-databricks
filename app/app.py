"""Laboratorio de IA · La Tinka

AI Functions de Databricks sobre los textos de la mesa de servicio, sin escribir SQL.
Cada pestaña tiene un botón "Ver SQL" con la llamada exacta a la función.
"""

import json
import re
import time
import unicodedata
import uuid

import altair as alt
import pandas as pd
import streamlit as st

from db import MODELO, T, consultar, ejecutar, lit

st.set_page_config(page_title="Laboratorio de IA · La Tinka", page_icon="🧪", layout="wide")

MAX_TEXTO = 1000
MAX_ENVIOS = 5
ESPERA_S = 8  # cooldown entre llamadas a la IA por persona
SENTIMIENTO_ES = {"positive": "positivo", "neutral": "neutral", "mixed": "mixto", "negative": "negativo"}
COLOR_SENTIMIENTO = {"positivo": "#00A972", "neutral": "#9AA7AD", "mixto": "#FFB547", "negativo": "#E8604D"}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=DM+Mono&display=swap');
html, body, [class*="css"], .stMarkdown, .stButton button, .stTextInput input, .stTextArea textarea { font-family: 'DM Sans', sans-serif; }
code, pre { font-family: 'DM Mono', monospace !important; }
h1, h2, h3 { color: #0B2026; letter-spacing: -0.01em; }
.etiqueta { display:inline-block; padding:2px 10px; border-radius:12px; font-size:0.85rem; font-weight:500; }
.positive { background:#E3F4EC; color:#00694A; } .negative { background:#FDE7E4; color:#A1220F; }
.neutral { background:#EEF1F2; color:#3E5059; } .mixed { background:#FFF3D6; color:#7A5300; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- utilidades
def usuario() -> str:
    # Solo identificación para el marcador; la autorización la da el service principal de la app
    return st.context.headers.get("X-Forwarded-Email") or "invitado@local"


def nombre_corto(email: str) -> str:
    return email.split("@")[0].replace(".", " ").title()


def puede_llamar() -> bool:
    ultimo = st.session_state.get("ultima_llamada", 0.0)
    falta = ESPERA_S - (time.time() - ultimo)
    if falta > 0:
        st.warning(f"Espera {falta:.0f} segundos antes de volver a llamar a la IA.")
        return False
    st.session_state["ultima_llamada"] = time.time()
    return True


def ver_sql(sentencia: str):
    with st.expander("Ver SQL"):
        st.code(sentencia.strip(), language="sql")


def normalizar(texto) -> str:
    if texto is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


def a_numero(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    m = re.search(r"\d[\d,\.]*", str(valor))
    return float(m.group().replace(",", "")) if m else None


def respuesta_ia(crudo):
    """Las AI Functions v2 devuelven {"response": ..., "error_message": ...}."""
    try:
        return json.loads(crudo).get("response")
    except (TypeError, ValueError, AttributeError):
        return crudo


def envios(ronda: int) -> int:
    df = consultar(f"SELECT COUNT(*) AS n FROM {T}.reto_intentos WHERE email = :email AND ronda = :ronda",
                   {"email": usuario(), "ronda": ronda})
    return int(df["n"][0])


def guardar_intento(ronda: int, propuesta, resultado, puntaje: float):
    ejecutar(f"INSERT INTO {T}.reto_intentos VALUES (:id, :email, :ronda, current_timestamp(), :propuesta, :resultado, :puntaje)",
             {"id": uuid.uuid4().hex, "email": usuario(), "ronda": ronda, "propuesta": json.dumps(propuesta, ensure_ascii=False),
              "resultado": json.dumps(resultado, ensure_ascii=False, default=str), "puntaje": float(puntaje)})


@st.cache_data(ttl=600, show_spinner=False)
def leer(sentencia: str) -> pd.DataFrame:
    return consultar(sentencia)


# ---------------------------------------------------------------- encabezado
col_a, col_b = st.columns([4, 1])
col_a.title("🧪 Laboratorio de IA · La Tinka")
col_a.caption("Funciones de IA de Databricks aplicadas a los textos de la mesa de servicio, sin escribir código.")
col_b.markdown(f"<div style='text-align:right;padding-top:28px;color:#5A6F77'>👤 {nombre_corto(usuario())}</div>",
               unsafe_allow_html=True)

tabs = st.tabs(["1 · Sentimiento", "2 · Clasificar", "3 · Extraer", "4 · Resumir y traducir", "5 · Prompt libre", "🏆 Reto"])

# ---------------------------------------------------------------- 1. Sentimiento
with tabs[0]:
    st.subheader("¿Cómo se sienten los usuarios?")
    st.write("Cada comentario de las encuestas pasó por `ai_analyze_sentiment`, que devuelve positivo, negativo, neutral o mixto.")
    df = leer(f"SELECT equipo, categoria, fecha_encuesta, calificacion, comentario, sentimiento FROM {T}.encuestas_sentimiento")
    equipos = ["Todos"] + sorted(df["equipo"].unique())
    c1, c2 = st.columns([1, 3])
    equipo = c1.selectbox("Equipo", equipos)
    vista = df if equipo == "Todos" else df[df["equipo"] == equipo]
    conteo = df.groupby(["equipo", "sentimiento"]).size().reset_index(name="comentarios")
    conteo["sentimiento"] = conteo["sentimiento"].map(SENTIMIENTO_ES).fillna(conteo["sentimiento"])
    c2.markdown("**% de comentarios por sentimiento y equipo**")
    c2.altair_chart(
        alt.Chart(conteo).mark_bar().encode(
            x=alt.X("comentarios:Q", stack="normalize", title=None, axis=alt.Axis(format="%")),
            y=alt.Y("equipo:N", title=None, axis=alt.Axis(labelLimit=220)),
            color=alt.Color("sentimiento:N", title=None, legend=alt.Legend(orient="bottom"),
                            scale=alt.Scale(domain=list(COLOR_SENTIMIENTO), range=list(COLOR_SENTIMIENTO.values()))),
            order=alt.Order("orden:Q"),
            tooltip=["equipo", "sentimiento", "comentarios"],
        ).transform_calculate(orden=f"indexof({list(COLOR_SENTIMIENTO)}, datum.sentimiento)").properties(height=280),
        use_container_width=True)
    st.markdown(f"**Comentarios** ({len(vista):,})")
    muestra = vista.sort_values("fecha_encuesta", ascending=False).head(25)
    for _, r in muestra.iterrows():
        st.markdown(f"<span class='etiqueta {r.sentimiento}'>{SENTIMIENTO_ES.get(r.sentimiento, r.sentimiento)}</span> &nbsp;{r.comentario} "
                    f"<span style='color:#8A9AA1'>· {r.equipo} · {r.calificacion}★</span>", unsafe_allow_html=True)
    ver_sql(f"SELECT comentario, ai_analyze_sentiment(comentario) AS sentimiento\nFROM {T}.encuestas_satisfaccion")

# ---------------------------------------------------------------- 2. Clasificar
with tabs[1]:
    st.subheader("Clasifica una incidencia")
    st.write("`ai_classify` elige la etiqueta que mejor describe el texto. Las descripciones de cada etiqueta ayudan mucho.")
    ejemplos = leer(f"SELECT DISTINCT descripcion FROM {T}.incidencias ORDER BY descripcion LIMIT 40")["descripcion"].tolist()
    st.session_state.setdefault("clas_txt", ejemplos[0])
    st.selectbox("Elige un ejemplo o escribe el tuyo abajo", ejemplos, index=0, key="clas_ej",
                 on_change=lambda: st.session_state.update(clas_txt=st.session_state["clas_ej"]))
    texto = st.text_area("Texto de la incidencia", max_chars=MAX_TEXTO, key="clas_txt")
    etiquetas_txt = st.text_area(
        "Etiquetas (una por línea, formato `etiqueta: descripción`)",
        "pagos y premios: problemas con cobros, retiros, recargas o pago de premios\n"
        "acceso a cuenta: contraseña, bloqueo, códigos de verificación\n"
        "app y web: fallas de la aplicación o página web\n"
        "punto de venta: agencias, agentes y terminales\n"
        "infraestructura: servidores, redes y sistemas internos",
        height=150, key="clas_etq")
    etiquetas = {}
    for linea in etiquetas_txt.splitlines():
        if linea.strip():
            nombre, _, desc = linea.partition(":")
            etiquetas[nombre.strip()[:50]] = (desc.strip() or nombre.strip())[:200]
    sentencia = f"SELECT ai_classify(:texto, {lit(json.dumps(etiquetas, ensure_ascii=False))}) AS resultado"
    if st.button("Clasificar", type="primary", key="clas_btn") and texto.strip() and 2 <= len(etiquetas) <= 20 and puede_llamar():
        with st.spinner("La IA está leyendo el texto…"):
            r = respuesta_ia(consultar(sentencia, {"texto": texto})["resultado"][0])
        st.success(f"Etiqueta: **{r[0] if isinstance(r, list) and r else r}**")
    ver_sql(sentencia.replace(":texto", lit(texto[:80] + ("…" if len(texto) > 80 else ""))))

# ---------------------------------------------------------------- 3. Extraer
with tabs[2]:
    st.subheader("Extrae datos de un texto libre")
    st.write("`ai_extract` lee el texto y devuelve los campos que le pidas, listos para un reporte.")
    texto = st.text_area("Texto del ticket", "Hola, ayer en la agencia de Miraflores compré una jugada de Kábala por S/ 12 "
                         "y el ticket salió en blanco. Quiero que me devuelvan mi dinero.", max_chars=MAX_TEXTO, key="ext_txt")
    campos = st.data_editor(pd.DataFrame([
        {"campo": "canal", "descripcion": "por dónde llegó: app, web, punto de venta, call center"},
        {"campo": "producto", "descripcion": "juego de La Tinka mencionado"},
        {"campo": "monto", "descripcion": "monto en soles, solo el número"},
    ]), num_rows="dynamic", use_container_width=True, key="ext_campos")
    esquema = {str(r.campo).strip()[:40]: {"type": "string", "description": str(r.descripcion or "")[:200]}
               for r in campos.itertuples() if str(r.campo).strip() and str(r.campo) != "nan"}
    sentencia = f"SELECT ai_extract(:texto, {lit(json.dumps(esquema, ensure_ascii=False))}) AS resultado"
    if st.button("Extraer", type="primary", key="ext_btn") and texto.strip() and esquema and puede_llamar():
        with st.spinner("Extrayendo…"):
            r = respuesta_ia(consultar(sentencia, {"texto": texto})["resultado"][0]) or {}
        st.dataframe(pd.DataFrame([{"campo": k, "valor": (v or {}).get("value") if isinstance(v, dict) else v}
                                   for k, v in r.items()]), hide_index=True, use_container_width=True)
    ver_sql(sentencia.replace(":texto", "'…'"))

# ---------------------------------------------------------------- 4. Resumir y traducir
with tabs[3]:
    st.subheader("Resumen semanal de comentarios negativos")
    st.write("`ai_summarize` condensa todos los comentarios de 1–2 estrellas de la semana; `ai_translate` lo deja en español y lo pasa a inglés.")
    df = leer(f"SELECT semana, comentarios, resumen, resumen_en FROM {T}.resumen_negativos_semana ORDER BY semana DESC")
    if df.empty:
        st.info("Aún no hay resúmenes.")
    else:
        df["etiqueta"] = pd.to_datetime(df["semana"]).dt.strftime("Semana del %d/%m/%Y")
        sel = st.selectbox("Semana", df["etiqueta"])
        fila = df[df["etiqueta"] == sel].iloc[0]
        idioma = st.radio("Idioma", ["Español", "English"], horizontal=True)
        st.info(fila.resumen if idioma == "Español" else fila.resumen_en)
        st.caption(f"Resumen de {fila.comentarios} comentarios negativos.")
    ver_sql(f"""WITH semanas AS (
  SELECT date_trunc('WEEK', fecha_encuesta) AS semana,
         ai_translate(ai_summarize(concat_ws(' | ', collect_list(comentario)), 60), 'es') AS resumen
  FROM {T}.encuestas_satisfaccion
  WHERE calificacion <= 2
  GROUP BY 1)
SELECT semana, resumen, ai_translate(resumen, 'en') AS resumen_en FROM semanas""")

# ---------------------------------------------------------------- 5. Prompt libre
with tabs[4]:
    st.subheader("Dale tu propia instrucción a la IA")
    st.write(f"`ai_query` envía tu instrucción a un modelo de lenguaje ({MODELO}) junto con el comentario elegido.")
    negativos = leer(f"SELECT DISTINCT comentario FROM {T}.encuestas_satisfaccion WHERE calificacion <= 2 ORDER BY comentario")["comentario"].tolist()
    comentario = st.selectbox("Comentario del cliente", negativos, key="pl_com")
    instruccion = st.text_area("Tu instrucción", "Redacta una respuesta empática y breve al cliente, en nombre de La Tinka, "
                               "ofreciendo un siguiente paso concreto.", max_chars=MAX_TEXTO, key="pl_ins")
    sentencia = (f"SELECT ai_query('{MODELO}', concat(:instruccion, '\\n\\nComentario del cliente: ', :comentario)) AS respuesta")
    if st.button("Enviar a la IA", type="primary", key="pl_btn") and instruccion.strip() and puede_llamar():
        with st.spinner("Escribiendo…"):
            st.markdown(consultar(sentencia, {"instruccion": instruccion, "comentario": comentario})["respuesta"][0])
    ver_sql(sentencia.replace(":instruccion", lit(instruccion[:60] + "…")).replace(":comentario", lit(comentario)))

# ---------------------------------------------------------------- 6. Reto
with tabs[5]:
    st.subheader("🏆 El mejor clasificador de La Tinka")
    ronda = st.radio("Ronda", ["1 · Explica las categorías ⭐", "2 · Extrae los datos ⭐⭐", "3 · Responde como La Tinka ⭐⭐⭐",
                               "Votación de la ronda 3", "Marcador"], horizontal=True, label_visibility="collapsed")

    # ---------- Ronda 1
    if ronda.startswith("1"):
        st.markdown("La app tiene **30 incidencias** y sabe a qué categoría pertenece cada una. Las categorías son estas 5. "
                    "**Explícale a la IA qué entra en cada categoría**, como se lo explicarías a un compañero nuevo. "
                    f"Punto por acierto (máximo 30). Cuenta tu mejor intento; tienes {MAX_ENVIOS} envíos.")
        reales = sorted(leer(f"SELECT DISTINCT categoria_real FROM {T}.reto_clasificacion_gold")["categoria_real"])
        with st.expander("💡 Pista"):
            st.markdown("Así se ve una incidencia y la categoría que le corresponde:\n\n"
                        "- «No me llegó el pago del premio de Kábala a mi cuenta BCP» → **Pagos y premios**\n"
                        "- «El agente de Piura dice que el sistema está caído y no vende Tinka» → **Punto de venta**\n\n"
                        "Menciona ejemplos concretos de lo que entra en cada categoría (por ejemplo: retiros, recargas, cobro de premios). "
                        "Si un caso podría caer en dos categorías, aclara en cuál va.")
        descripciones = {}
        for categoria in reales:
            c1, c2 = st.columns([1, 3])
            c1.markdown(f"<div style='padding-top:8px'><b>{categoria}</b></div>", unsafe_allow_html=True)
            descripciones[categoria] = c2.text_input(f"Descripción de {categoria}", key=f"r1_{categoria}", max_chars=200,
                                                     label_visibility="collapsed", placeholder="¿Qué incidencias entran aquí?").strip()
        # Sin descripción, la IA solo ve el nombre de la categoría
        etiquetas = {cat: (desc or cat) for cat, desc in descripciones.items()}
        sentencia = (f"SELECT id_reto, descripcion, categoria_real, ai_classify(descripcion, {lit(json.dumps(etiquetas, ensure_ascii=False))}) AS prediccion\n"
                     f"FROM {T}.reto_clasificacion_gold")
        usados = envios(1)
        contador = st.empty()
        contador.caption(f"Envíos usados: {usados}/{MAX_ENVIOS}")
        if st.button("Enviar propuesta", type="primary", disabled=usados >= MAX_ENVIOS, key="r1_btn") and puede_llamar():
            with st.spinner("Clasificando las 30 incidencias…"):
                df = consultar(sentencia)
            df["categoria_ia"] = df["prediccion"].map(lambda x: (respuesta_ia(x) or [None])[0])
            df["acierto"] = df["categoria_ia"] == df["categoria_real"]
            aciertos = int(df["acierto"].sum())
            contador.caption(f"Envíos usados: {usados + 1}/{MAX_ENVIOS}")
            guardar_intento(1, {"descripciones": descripciones}, {"aciertos": aciertos}, aciertos)
            st.metric("Aciertos", f"{aciertos} / 30", f"{aciertos / 30:.0%}")
            st.dataframe(df.groupby("categoria_real")["acierto"].agg(["sum", "count"])
                         .rename(columns={"sum": "aciertos", "count": "incidencias"}).rename_axis("categoría"), use_container_width=True)
            fallos = df[~df["acierto"]]
            if not fallos.empty:
                st.markdown("**Dónde se equivocó la IA** (úsalo para mejorar tus descripciones)")
                st.dataframe(fallos[["descripcion", "categoria_real", "categoria_ia"]]
                             .rename(columns={"descripcion": "incidencia", "categoria_real": "categoría correcta", "categoria_ia": "la IA dijo"}),
                             hide_index=True, use_container_width=True)
        ver_sql(sentencia)

    # ---------- Ronda 2
    elif ronda.startswith("2"):
        st.markdown("Sobre **10 tickets** de texto libre hay que obtener tres datos: el **canal** por el que llegó, el **juego** "
                    "y el **monto reclamado**. Tú decides cómo se llama cada campo y cómo se lo explicas a la IA. "
                    f"Punto por campo correcto (máximo 30). Tienes {MAX_ENVIOS} envíos.")
        with st.expander("💡 Pista"):
            st.markdown("Así se ve un ticket y los datos que hay que sacar:\n\n"
                        "- «Desde la app pagué S/ 15 por una Kábala y la jugada no aparece» → canal: **app** · juego: **Kábala** · monto reclamado: **15**\n"
                        "- «Por WhatsApp pregunté los resultados del Ganadiario de ayer» → canal: **whatsapp** · juego: **Ganadiario** · monto reclamado: **(vacío)**\n\n"
                        "Los canales correctos son palabras simples como «app» o «web». Si en la descripción enumeras los "
                        "valores posibles, la IA los respeta. Para el monto, pide solo el número.")
        ejemplo = leer(f"SELECT texto FROM {T}.reto_extraccion_gold ORDER BY id_reto LIMIT 2")["texto"].tolist()
        st.caption("Ejemplos de tickets: " + " · ".join(f"«{e}»" for e in ejemplo))
        objetivo = {"canal": "string", "juego": "string", "monto_reclamado": "number"}
        definicion = {}
        for clave, tipo in objetivo.items():
            c1, c2 = st.columns([1, 3])
            nombre = c1.text_input(f"Nombre del campo para **{clave.replace('_', ' ')}**", key=f"r2_n_{clave}", max_chars=40)
            desc = c2.text_input("Descripción para la IA", key=f"r2_d_{clave}", max_chars=200)
            definicion[clave] = (nombre.strip(), desc.strip(), tipo)
        esquema = {n: {"type": t, "description": d} if d else {"type": t} for n, d, t in definicion.values() if n}
        sentencia = (f"SELECT id_reto, ai_extract(texto, {lit(json.dumps(esquema, ensure_ascii=False))}) AS extraccion,\n"
                     f"       canal, juego, monto_reclamado\nFROM {T}.reto_extraccion_gold")
        usados = envios(2)
        contador = st.empty()
        contador.caption(f"Envíos usados: {usados}/{MAX_ENVIOS}")
        if st.button("Enviar propuesta", type="primary", disabled=usados >= MAX_ENVIOS, key="r2_btn"):
            nombres = [n for n, _, _ in definicion.values()]
            if not all(nombres) or len(set(nombres)) < 3:
                st.error("Ponle un nombre distinto a cada uno de los tres campos.")
            elif puede_llamar():
                with st.spinner("Extrayendo datos de los 10 tickets…"):
                    df = consultar(sentencia)
                filas, aciertos = [], 0
                for r in df.itertuples():
                    salida = respuesta_ia(r.extraccion) or {}
                    def valor(clave):
                        v = salida.get(definicion[clave][0])
                        return v.get("value") if isinstance(v, dict) else v
                    canal, juego, monto = valor("canal"), valor("juego"), a_numero(valor("monto_reclamado"))
                    ok_canal = bool(normalizar(canal)) and (normalizar(r.canal) in normalizar(canal) or normalizar(canal) in normalizar(r.canal))
                    # tolerante a plurales y palabras extra: "Raspadita premiada" cuenta como "Raspaditas"
                    ok_juego = bool(normalizar(juego)) and normalizar(r.juego).rstrip("s") in normalizar(juego)
                    ok_monto = (pd.isna(r.monto_reclamado) and not monto) or (monto is not None and not pd.isna(r.monto_reclamado) and abs(monto - r.monto_reclamado) < 0.01)
                    aciertos += ok_canal + ok_juego + ok_monto
                    filas.append({"ticket": r.id_reto, "canal": f"{'✅' if ok_canal else '❌'} {canal}", "juego": f"{'✅' if ok_juego else '❌'} {juego}",
                                  "monto": f"{'✅' if ok_monto else '❌'} {monto}"})
                contador.caption(f"Envíos usados: {usados + 1}/{MAX_ENVIOS}")
                guardar_intento(2, esquema, {"aciertos": aciertos}, aciertos)
                st.metric("Campos correctos", f"{aciertos} / 30", f"{aciertos / 30:.0%}")
                st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True)
        ver_sql(sentencia)

    # ---------- Ronda 3
    elif ronda.startswith("3"):
        caso = leer(f"SELECT comentario FROM {T}.reto_respuesta_casos ORDER BY id_reto LIMIT 1")["comentario"][0]
        st.markdown("Escribe la instrucción para que la IA responda a este cliente. El grupo votará la respuesta **más creativa**. "
                    "**5 puntos por voto.** En la votación se muestra tu último envío.")
        st.info(f"💬 «{caso}»")
        with st.expander("💡 Pista"):
            st.markdown("Dos ideas para arrancar (no las copies, ¡inventa la tuya!):\n\n"
                        "- «Responde como el locutor del sorteo de La Tinka, con mucha emoción y en 3 líneas.»\n"
                        "- «Escribe la respuesta como un mensaje de WhatsApp cercano, con una frase de buena suerte al final.»\n\n"
                        "Combina un personaje, un formato y un toque tuyo.")
        instruccion = st.text_area("Tu instrucción para la IA", max_chars=MAX_TEXTO, key="r3_ins",
                                   placeholder="Ej.: Responde como si fueras…")
        sentencia = f"SELECT ai_query('{MODELO}', concat(:instruccion, '\\n\\nComentario del cliente: ', :comentario)) AS respuesta"
        usados = envios(3)
        contador = st.empty()
        contador.caption(f"Envíos usados: {usados}/{MAX_ENVIOS}")
        if st.button("Generar y enviar", type="primary", disabled=usados >= MAX_ENVIOS, key="r3_btn") and instruccion.strip() and puede_llamar():
            with st.spinner("Generando respuesta…"):
                respuesta = consultar(sentencia, {"instruccion": instruccion, "comentario": caso})["respuesta"][0]
            contador.caption(f"Envíos usados: {usados + 1}/{MAX_ENVIOS}")
            guardar_intento(3, {"instruccion": instruccion}, {"respuesta": respuesta}, 0)
            st.markdown("**Respuesta enviada a votación:**")
            st.markdown(respuesta)
        ver_sql(sentencia.replace(":comentario", lit(caso)).replace(":instruccion", "'<tu instrucción>'"))

    # ---------- Votación
    elif ronda.startswith("Votación"):
        st.markdown("Lee las respuestas (anónimas) y vota por la **más creativa**. No puedes votar por la tuya; puedes cambiar tu voto.")
        df = consultar(f"""
            SELECT id_intento, email, get_json_object(resultado, '$.respuesta') AS respuesta
            FROM (SELECT *, row_number() OVER (PARTITION BY email ORDER BY ts DESC) AS n FROM {T}.reto_intentos WHERE ronda = 3)
            WHERE n = 1 ORDER BY id_intento""")
        mi_voto = consultar(f"SELECT id_intento FROM {T}.reto_votos WHERE email = :email", {"email": usuario()})
        mi_voto = mi_voto["id_intento"][0] if not mi_voto.empty else None
        if df.empty:
            st.info("Todavía no hay respuestas en la ronda 3.")
        for i, r in enumerate(df.itertuples(), 1):
            with st.container(border=True):
                st.markdown(f"**Respuesta {i}**" + (" · ✅ tu voto" if r.id_intento == mi_voto else ""))
                st.markdown(r.respuesta)
                if r.email != usuario() and r.id_intento != mi_voto and st.button("Votar por esta", key=f"voto_{r.id_intento}"):
                    ejecutar(f"DELETE FROM {T}.reto_votos WHERE email = :email", {"email": usuario()})
                    ejecutar(f"INSERT INTO {T}.reto_votos VALUES (:email, :id, current_timestamp())", {"email": usuario(), "id": r.id_intento})
                    st.rerun()

    # ---------- Marcador
    else:
        @st.fragment(run_every=10)
        def marcador():
            df = consultar(f"""
                WITH r12 AS (SELECT email, ronda, MAX(puntaje) AS puntos FROM {T}.reto_intentos WHERE ronda IN (1, 2) GROUP BY email, ronda),
                     r3 AS (SELECT i.email, 5 * COUNT(v.email) AS puntos FROM {T}.reto_intentos i
                            JOIN {T}.reto_votos v ON v.id_intento = i.id_intento GROUP BY i.email),
                     todos AS (SELECT DISTINCT email FROM {T}.reto_intentos)
                SELECT t.email,
                       COALESCE(MAX(CASE WHEN r12.ronda = 1 THEN r12.puntos END), 0) AS ronda_1,
                       COALESCE(MAX(CASE WHEN r12.ronda = 2 THEN r12.puntos END), 0) AS ronda_2,
                       COALESCE(MAX(r3.puntos), 0) AS ronda_3
                FROM todos t LEFT JOIN r12 ON t.email = r12.email LEFT JOIN r3 ON t.email = r3.email
                GROUP BY t.email""")
            if df.empty:
                st.info("Aún no hay envíos. ¡El primero en enviar estrena el marcador!")
                return
            df["total"] = df[["ronda_1", "ronda_2", "ronda_3"]].sum(axis=1)
            df = df.sort_values("total", ascending=False).reset_index(drop=True)
            df.insert(0, "#", ["🥇", "🥈", "🥉"][: min(3, len(df))] + [str(i) for i in range(4, len(df) + 1)])
            df["participante"] = df["email"].map(nombre_corto)
            st.dataframe(df[["#", "participante", "ronda_1", "ronda_2", "ronda_3", "total"]], hide_index=True, use_container_width=True,
                         column_config={"ronda_1": "Ronda 1 ⭐", "ronda_2": "Ronda 2 ⭐⭐", "ronda_3": "Ronda 3 ⭐⭐⭐",
                                        "total": st.column_config.ProgressColumn("Total", min_value=0, max_value=max(90, int(df["total"].max())), format="%d")})
            st.caption("Se actualiza solo cada 10 segundos.")

        marcador()
