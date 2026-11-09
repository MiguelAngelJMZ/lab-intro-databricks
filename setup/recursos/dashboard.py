"""Dashboard AI/BI "Mesa de servicio – Seguimiento" (3 páginas).

Las consultas usan nombres de tabla sin catálogo/esquema; cada dataset lleva
`catalog` y `schema` para que el mismo JSON sirva en cualquier workspace.
"""

import json
from datetime import date


def _pos(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def _texto(nombre, lineas, pos):
    return {"widget": {"name": nombre, "multilineTextboxSpec": {"lines": lineas}}, "position": pos}


def _filtro(nombre, titulo, campo, tipo, datasets, pos):
    return {
        "widget": {
            "name": nombre,
            "queries": [{"name": f"{nombre}_{ds}", "query": {"datasetName": ds, "fields": [{"name": campo, "expression": f"`{campo}`"}],
                                                          "disaggregated": False}} for ds in datasets],
            "spec": {"version": 2, "widgetType": tipo,
                     "encodings": {"fields": [{"fieldName": campo, "displayName": titulo, "queryName": f"{nombre}_{ds}"} for ds in datasets]},
                     "frame": {"showTitle": True, "title": titulo}},
        },
        "position": pos,
    }


def _kpi(nombre, titulo, ds, expr, pos, formato=None):
    valor = {"fieldName": nombre, "displayName": titulo}
    if formato:
        valor["format"] = formato
    return {
        "widget": {
            "name": nombre,
            "queries": [{"name": "main_query", "query": {"datasetName": ds, "fields": [{"name": nombre, "expression": expr}], "disaggregated": False}}],
            "spec": {"version": 2, "widgetType": "counter", "encodings": {"value": valor}, "frame": {"showTitle": True, "title": titulo}},
        },
        "position": pos,
    }


PCT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}


def construir(catalogo, esquema, fecha_taller: date, genie_id=None):
    hoy = f"DATE'{fecha_taller.isoformat()}'"

    datasets = [
        {"name": "ds_incidencias", "displayName": "incidencias", "queryLines": [
            "SELECT id_incidencia, fecha_apertura, fecha_cierre, prioridad, categoria, equipo, gerente, area, estatus, sla_horas, ",
            "       horas_resolucion, dentro_sla, ",
            "       CASE WHEN estatus <> 'Cerrada' THEN 1 ELSE 0 END AS es_abierta, ",
            "       CASE WHEN estatus = 'Cerrada' THEN 1 ELSE 0 END AS es_cerrada, ",
            "       CASE WHEN dentro_sla THEN 1.0 WHEN NOT dentro_sla THEN 0.0 END AS dentro_sla_num ",
            "FROM incidencias_sla",
        ]},
        {"name": "ds_proyectos", "displayName": "proyectos", "queryLines": [
            "SELECT id_proyecto, nombre, responsable, fecha_inicio, fecha_compromiso, pct_avance, estatus, ",
            f"       datediff(fecha_compromiso, {hoy}) AS dias_para_compromiso ",
            "FROM proyectos ORDER BY fecha_compromiso",
        ]},
        {"name": "ds_encuestas", "displayName": "encuestas_satisfaccion", "queryLines": [
            "SELECT e.id_incidencia, e.calificacion, e.comentario, e.fecha_encuesta, i.equipo, i.categoria, i.prioridad ",
            "FROM encuestas_satisfaccion e JOIN incidencias i ON e.id_incidencia = i.id_incidencia",
        ]},
    ]

    operacion = {
        "name": "operacion", "displayName": "Operación", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1",
        "layout": [
            _texto("titulo_operacion", ["# Mesa de servicio – Operación\n", "\n",
                                        f"Incidencias de TI de La Tinka. Fecha de referencia: {fecha_taller.strftime('%d/%m/%Y')}."], _pos(0, 0, 6, 2)),
            _filtro("filtro_equipo", "Equipo", "equipo", "filter-multi-select", ["ds_incidencias"], _pos(6, 0, 3, 2)),
            _filtro("filtro_fecha", "Fecha de apertura", "fecha_apertura", "filter-date-range-picker", ["ds_incidencias"], _pos(9, 0, 3, 2)),
            _kpi("kpi_abiertas", "Incidencias abiertas", "ds_incidencias", "SUM(`es_abierta`)", _pos(0, 2, 4, 3)),
            _kpi("kpi_cerradas", "Incidencias cerradas", "ds_incidencias", "SUM(`es_cerrada`)", _pos(4, 2, 4, 3)),
            _kpi("kpi_sla", "% dentro de SLA", "ds_incidencias", "AVG(`dentro_sla_num`)", _pos(8, 2, 4, 3), PCT),
            {
                "widget": {
                    "name": "tendencia_semanal",
                    "queries": [{"name": "main_query", "query": {"datasetName": "ds_incidencias", "fields": [
                        {"name": "weekly(fecha_apertura)", "expression": "DATE_TRUNC(\"WEEK\", `fecha_apertura`)"},
                        {"name": "count(id_incidencia)", "expression": "COUNT(`id_incidencia`)"}], "disaggregated": False}}],
                    "spec": {"version": 3, "widgetType": "line", "encodings": {
                        "x": {"fieldName": "weekly(fecha_apertura)", "scale": {"type": "temporal"}, "displayName": "Semana"},
                        "y": {"fieldName": "count(id_incidencia)", "scale": {"type": "quantitative"}, "displayName": "Incidencias"}},
                        "frame": {"showTitle": True, "title": "Incidencias abiertas por semana"}},
                },
                "position": _pos(0, 5, 7, 6),
            },
            {
                "widget": {
                    "name": "por_categoria",
                    "queries": [{"name": "main_query", "query": {"datasetName": "ds_incidencias", "fields": [
                        {"name": "categoria", "expression": "`categoria`"},
                        {"name": "count(id_incidencia)", "expression": "COUNT(`id_incidencia`)"}], "disaggregated": False}}],
                    "spec": {"version": 3, "widgetType": "bar", "encodings": {
                        "x": {"fieldName": "count(id_incidencia)", "scale": {"type": "quantitative"}, "displayName": "Incidencias"},
                        "y": {"fieldName": "categoria", "scale": {"type": "categorical"}, "displayName": "Categoría"},
                        "label": {"show": True}},
                        "frame": {"showTitle": True, "title": "Incidencias por categoría"}},
                },
                "position": _pos(7, 5, 5, 6),
            },
        ],
    }

    proyectos = {
        "name": "proyectos", "displayName": "Proyectos", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1",
        "layout": [
            _texto("titulo_proyectos", ["# Proyectos de TI\n", "\n", "Avance y fecha compromiso de cada proyecto."], _pos(0, 0, 12, 2)),
            _kpi("kpi_proyectos_activos", "Proyectos sin completar", "ds_proyectos",
                 "COUNT(CASE WHEN `estatus` <> 'Completado' THEN `id_proyecto` END)", _pos(0, 2, 6, 3)),
            _kpi("kpi_avance_promedio", "Avance promedio (sin completar)", "ds_proyectos",
                 "AVG(CASE WHEN `estatus` <> 'Completado' THEN `pct_avance` END)", _pos(6, 2, 6, 3),
                 {"type": "number-plain", "decimalPlaces": {"type": "max", "places": 0}, "suffix": "%"}),
            {
                "widget": {
                    "name": "tabla_proyectos",
                    "queries": [{"name": "main_query", "query": {"datasetName": "ds_proyectos", "fields": [
                        {"name": c, "expression": f"`{c}`"} for c in
                        ["nombre", "responsable", "estatus", "pct_avance", "fecha_compromiso", "dias_para_compromiso"]], "disaggregated": True}}],
                    "spec": {"version": 2, "widgetType": "table", "encodings": {"columns": [
                        {"fieldName": "nombre", "displayName": "Proyecto"},
                        {"fieldName": "responsable", "displayName": "Responsable"},
                        {"fieldName": "estatus", "displayName": "Estatus"},
                        {"fieldName": "pct_avance", "displayName": "% avance"},
                        {"fieldName": "fecha_compromiso", "displayName": "Fecha compromiso"},
                        {"fieldName": "dias_para_compromiso", "displayName": "Días para compromiso"},
                    ]}, "frame": {"showTitle": True, "title": "Proyectos"}},
                },
                "position": _pos(0, 5, 12, 9),
            },
        ],
    }

    satisfaccion = {
        "name": "satisfaccion", "displayName": "Satisfacción", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1",
        "layout": [
            _texto("titulo_satisfaccion", ["# Satisfacción de usuarios\n", "\n", "Encuestas de 1 a 5 al cerrar cada incidencia."], _pos(0, 0, 12, 2)),
            _kpi("kpi_calificacion", "Calificación promedio", "ds_encuestas", "AVG(`calificacion`)", _pos(0, 2, 6, 3),
                 {"type": "number-plain", "decimalPlaces": {"type": "exact", "places": 2}}),
            _kpi("kpi_encuestas", "Encuestas respondidas", "ds_encuestas", "COUNT(`id_incidencia`)", _pos(6, 2, 6, 3)),
            {
                "widget": {
                    "name": "calificacion_por_equipo",
                    "queries": [{"name": "main_query", "query": {"datasetName": "ds_encuestas", "fields": [
                        {"name": "equipo", "expression": "`equipo`"},
                        {"name": "avg(calificacion)", "expression": "AVG(`calificacion`)"}], "disaggregated": False}}],
                    "spec": {"version": 3, "widgetType": "bar", "encodings": {
                        "x": {"fieldName": "avg(calificacion)", "scale": {"type": "quantitative", "domainMin": 0, "domainMax": 5},
                              "displayName": "Calificación promedio",
                              "format": {"type": "number-plain", "decimalPlaces": {"type": "exact", "places": 2}}},
                        "y": {"fieldName": "equipo", "scale": {"type": "categorical"}, "displayName": "Equipo"},
                        "label": {"show": True}},
                        "frame": {"showTitle": True, "title": "Calificación promedio por equipo"}},
                },
                "position": _pos(0, 5, 12, 6),
            },
        ],
    }

    for ds in datasets:  # catálogo y esquema por dataset: las consultas usan nombres de tabla sin prefijo
        ds.update(catalog=catalogo, schema=esquema)

    tablero = {
        "datasets": datasets,
        "pages": [operacion, proyectos, satisfaccion],
        "uiSettings": {"theme": {
            "canvasBackgroundColor": {"light": "#F9F7F4", "dark": "#0B2026"},
            "widgetBackgroundColor": {"light": "#FFFFFF", "dark": "#11171C"},
            "widgetBorderColor": {"light": "#FFFFFF", "dark": "#11171C"},
            "fontColor": {"light": "#0B2026", "dark": "#E8ECF0"},
            "selectionColor": {"light": "#FF3621", "dark": "#FF5F46"},
            "visualizationColors": ["#2272B4", "#FF5F46", "#00A972", "#7D5BA6", "#FFAB00", "#1B3139", "#AB4057"],
            "widgetHeaderAlignment": "LEFT",
            "fontFamily": "DM Sans",
            "widgetCornerRadius": 8,
        }},
    }
    if genie_id:
        tablero["uiSettings"]["genieSpace"] = {"isEnabled": True, "overrideId": genie_id, "enablementMode": "ENABLED"}
    return json.dumps(tablero, ensure_ascii=False)
