"""Genera las tarjetas del Lab 1 ("Genie al revés") a partir de las respuestas reales.

Uso:
    python3 generar_tarjetas.py lab1_respuestas.json

`lab1_respuestas.json` sale de la tabla taller_config (claves lab1_tarjeta_N) que deja
el notebook de setup. Produce dos archivos junto al JSON:
  - tarjetas_lab1.html             para participantes (sin la pregunta, pistas ocultas)
  - tarjetas_lab1_instructor.html  con la pregunta solución
Ábrelos en Chrome; para imprimir usa Cmd+P con "Gráficos de fondo" activado.
"""

import html
import json
import sys
from datetime import date
from pathlib import Path

NIVELES = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3}
# Siempre visible: qué representa el resultado (unidad, forma, ejes o columnas), sin dar la pregunta
FICHA = {
    1: "Un solo número. Unidad: incidencias. Corresponde a un mes calendario completo.",
    2: "Tabla de 5 filas: una por equipo, con su número de incidencias. Ordenada de mayor a menor.",
    3: "Una barra por categoría. Cada barra es un porcentaje de 0 a 100 sobre incidencias ya cerradas.",
    4: "Un punto por semana (las semanas empiezan en lunes): 13 semanas completas, del 24/08 al 16/11.",
    5: "4 proyectos con su responsable y su % de avance, ordenados de menor a mayor avance.",
    6: "Un equipo y cuánto cambió su calificación promedio de satisfacción (escala de 1 a 5) entre dos meses.",
}
# Pistas gratis, de la más general a la más específica
PISTAS = {
    1: ["Cuenta incidencias que se abrieron (se registraron), sin importar si ya se cerraron.",
        "El periodo es el mes pasado."],
    2: ["Solo cuentan incidencias de prioridad P1 (las urgentes).",
        "Solo las que todavía no están cerradas."],
    3: ["El porcentaje mide cuántas se resolvieron dentro del tiempo comprometido (SLA).",
        "Se calcula para cada categoría."],
    4: ["Cada punto cuenta las incidencias nuevas que se abrieron en esa semana.",
        "El periodo son los últimos 3 meses."],
    5: ["Todos vencen (fecha compromiso) en los próximos 30 días.",
        "Todos llevan menos del 50% de avance."],
    6: ["Compara la satisfacción del mes pasado contra la del mes anterior.",
        "Es el equipo con la mayor caída. La satisfacción está en las encuestas y el equipo en las incidencias."],
}
SOLUCIONES = {
    1: "¿Cuántas incidencias se abrieron el mes pasado?",
    2: "¿Cuántas incidencias P1 siguen abiertas por equipo?",
    3: "¿Qué % de incidencias se cerró dentro del SLA por categoría?",
    4: "Tendencia semanal de incidencias nuevas de los últimos 3 meses",
    5: "Proyectos con fecha compromiso en los próximos 30 días y avance menor a 50%",
    6: "¿Qué equipo tuvo la mayor caída en satisfacción promedio el mes pasado respecto al mes anterior?",
}
FORMA = {1: "Un número", 2: "Tabla", 3: "Barras horizontales", 4: "Línea semanal", 5: "Lista", 6: "Un equipo y su variación"}
NAVY, LAVA, AZURE = "#0B2026", "#FF3621", "#2272B4"


def estrellas(n):
    estrella = ('<svg width="18" height="18" viewBox="0 0 24 24"><path fill="{c}" d="M12 2l2.9 6.9 7.1.6-5.4 4.7 1.7 7-6.3-3.9-6.3 3.9 1.7-7L2 9.5l7.1-.6z"/></svg>')
    return "".join(estrella.format(c="#F5B400" if i < n else "#DCD9D3") for i in range(3))


def tabla(filas, columnas):
    cab = "".join(f"<th>{html.escape(t)}</th>" for _, t in columnas)
    cuerpo = "".join("<tr>" + "".join(f"<td>{html.escape(str(f[c]))}</td>" for c, _ in columnas) + "</tr>" for f in filas)
    return f"<table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table>"


def barras(filas, etiqueta, valor, sufijo=""):
    maximo = max(f[valor] for f in filas)
    alto, ancho_etq, ancho = 34, 170, 330
    svg = [f'<svg viewBox="0 0 {ancho_etq + ancho + 60} {alto * len(filas)}" width="100%">']
    for i, f in enumerate(filas):
        y = i * alto
        w = ancho * f[valor] / maximo
        svg.append(f'<text x="{ancho_etq - 10}" y="{y + 22}" text-anchor="end" font-size="14" fill="{NAVY}">{html.escape(f[etiqueta])}</text>'
                   f'<rect x="{ancho_etq}" y="{y + 7}" width="{w:.1f}" height="20" rx="3" fill="{AZURE}"/>'
                   f'<text x="{ancho_etq + w + 8:.1f}" y="{y + 22}" font-size="14" fill="{NAVY}">{f[valor]}{sufijo}</text>')
    svg.append("</svg>")
    return "".join(svg)


def linea(filas):
    valores = [f["incidencias"] for f in filas]
    ancho, alto, m = 520, 220, 36
    lo, hi = 0, max(valores) * 1.15
    x = lambda i: m + i * (ancho - 2 * m) / (len(valores) - 1)
    y = lambda v: alto - m - (v - lo) / (hi - lo) * (alto - 2 * m)
    puntos = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(valores))
    svg = [f'<svg viewBox="0 0 {ancho} {alto}" width="100%">',
           f'<line x1="{m}" y1="{alto - m}" x2="{ancho - m}" y2="{alto - m}" stroke="#BFC5C7"/>',
           f'<polyline points="{puntos}" fill="none" stroke="{AZURE}" stroke-width="3" stroke-linejoin="round"/>']
    for i, (f, v) in enumerate(zip(filas, valores)):
        svg.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" fill="{AZURE}"/>')
        if i % 3 == 0 or i == len(valores) - 1:
            d = date.fromisoformat(f["semana"][:10])
            svg.append(f'<text x="{x(i):.1f}" y="{alto - m + 18}" font-size="12" text-anchor="middle" fill="#5B7079">{d.strftime("%d/%m")}</text>')
    svg.append(f'<text x="{m}" y="18" font-size="12" fill="#5B7079">{len(valores)} semanas · eje Y: incidencias</text></svg>')
    return "".join(svg)


def resultado(n, filas):
    if n == 1:
        return f'<div class="numero">{filas[0]["incidencias"]}</div>'
    if n == 2:
        return tabla(filas, [("equipo", "equipo"), ("incidencias", "incidencias")])
    if n == 3:
        return barras(filas, "categoria", "pct_dentro_sla", "%")
    if n == 4:
        return linea(filas)
    if n == 5:
        return tabla(filas, [("nombre", "proyecto"), ("responsable", "responsable"), ("pct_avance", "% avance")])
    f = filas[0]
    return f'<div class="numero chico">{html.escape(f["equipo"])}<br><span>{f["variacion"]:+.2f} pts</span></div>'


def pagina(respuestas, instructor):
    tarjetas = []
    for n in range(1, 7):
        extra = (f'<div class="solucion">Pregunta solución: <b>{SOLUCIONES[n]}</b></div>' if instructor else "")
        tarjetas.append(f"""
<article class="tarjeta">
  <header><span class="num">Tarjeta {n}</span><span>{estrellas(NIVELES[n])}</span></header>
  <div class="forma">{FORMA[n]}</div>
  <div class="resultado">{resultado(n, respuestas[str(n)])}</div>
  <p class="ficha"><b>Qué muestra:</b> {FICHA[n]}</p>
  {''.join(f"<details{' open' if instructor else ''}><summary>Pista {k}</summary><p>{p}</p></details>" for k, p in enumerate(PISTAS[n], 1))}
  {extra}
</article>""")
    titulo = "Lab 1 · Tarjetas de respuesta" + (" · Instructor" if instructor else "")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{titulo}</title>
<style>
body {{ font-family: 'DM Sans', Arial, sans-serif; color: {NAVY}; background: #F9F7F4; margin: 32px; }}
h1 {{ font-size: 28px; margin: 0 0 4px; }} .sub {{ color: #5B7079; margin: 0 0 24px; }}
.grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }}
.tarjeta {{ background: #fff; border: 1px solid #DCD9D3; border-radius: 12px; padding: 20px 24px; break-inside: avoid; }}
header {{ display: flex; justify-content: space-between; align-items: center; }}
.num {{ font-weight: 700; font-size: 18px; }} .num::before {{ content: ''; display: inline-block; width: 24px; height: 3px; background: {LAVA}; margin-right: 10px; vertical-align: middle; }}
.forma {{ font-family: 'DM Mono', monospace; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #5B7079; margin: 8px 0 12px; }}
.ficha {{ font-size: 14px; color: #2F4A52; background: #F9F7F4; border-radius: 8px; padding: 8px 12px; margin: 12px 0 0; }}
.resultado {{ min-height: 220px; display: flex; align-items: center; justify-content: center; }}
.numero {{ font-size: 96px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; text-align: center; }}
.numero.chico {{ font-size: 40px; line-height: 1.2; }} .numero span {{ font-size: 56px; color: {LAVA}; }}
table {{ border-collapse: collapse; width: 100%; font-size: 15px; }} th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid #EEEDE9; }}
th {{ font-family: 'DM Mono', monospace; font-size: 12px; color: #5B7079; font-weight: 400; }}
td:last-child, th:last-child {{ text-align: right; font-variant-numeric: tabular-nums; }}
details {{ margin-top: 8px; border-top: 1px dashed #DCD9D3; padding-top: 8px; }} details p {{ margin: 6px 0 0 18px; }} summary {{ cursor: pointer; color: {AZURE}; }}
.solucion {{ margin-top: 10px; background: #FFF3F0; border-radius: 8px; padding: 10px 12px; font-size: 14px; }}
.reglas {{ margin-top: 24px; font-size: 14px; color: #2F4A52; }}
@media print {{ body {{ margin: 12mm; background: #fff; }} details > p {{ display: block; }} summary small::after {{ content: ' (doblar)'; }} }}
</style></head><body>
<h1>{titulo}</h1>
<p class="sub">Escriban en Genie la pregunta que reproduce <b>exactamente</b> este resultado (mismos valores y misma forma).</p>
<div class="grid">{''.join(tarjetas)}</div>
<p class="reglas"><b>Cómo escribir la pregunta:</b> di qué cuentas o mides, cómo lo agrupas y de qué periodo. Las pistas son libres: úsalas cuando las necesites.<br>
Las estrellas indican la dificultad (1 a 3). Gana quien termine primero las 6 tarjetas.</p>
</body></html>"""


if __name__ == "__main__":
    origen = Path(sys.argv[1] if len(sys.argv) > 1 else "lab1_respuestas.json")
    respuestas = json.loads(origen.read_text())
    (origen.parent / "tarjetas_lab1.html").write_text(pagina(respuestas, instructor=False))
    (origen.parent / "tarjetas_lab1_instructor.html").write_text(pagina(respuestas, instructor=True))
    print("Listo:", origen.parent / "tarjetas_lab1.html", "y", origen.parent / "tarjetas_lab1_instructor.html")
