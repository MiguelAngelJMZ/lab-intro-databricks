# Taller de iniciación en Databricks – La Tinka

Todo lo necesario para el taller del **26 de noviembre de 2026**: presentación, laboratorio y materiales.

```
TallerNoTecnico/
├── presentacion/taller-la-tinka.html   Presentación (abrir en Chrome; F = pantalla completa)
├── setup/00_setup_taller               Notebook que crea todo el laboratorio
├── setup/99_limpieza                   Notebook que borra todo después del taller
├── setup/recursos/                     Datos sintéticos, Genie, dashboard (lo usa el setup)
├── app/                                App "Laboratorio de IA" (la despliega el setup)
└── materiales/                         Tarjetas del Lab 1, reto del Lab 2, guía del participante
```

El material del instructor (guía, solucionario del reto y tarjetas con las preguntas solución) no está en este repositorio.

## Preparar el laboratorio en el workspace de La Tinka

**Antes de empezar**, el equipo de La Tinka necesita:

1. Un workspace con **Unity Catalog** y **SQL Warehouse serverless** habilitados.
2. **Genie, Dashboards AI/BI, Databricks Assistant y las funciones de IA** habilitados.
3. Un **grupo de cuenta** con los participantes (por ejemplo `taller_iniciacion`), asignado al workspace. Cada participante debe haber iniciado sesión al menos una vez.
4. Que la persona que corra el setup sea **administradora del workspace** y pueda crear catálogos.

**Pasos:**

1. Subir las carpetas `setup/` y `app/` al workspace, juntas y dentro de la misma carpeta padre. Hay dos formas:
   - **Git folder:** si el material está en un repositorio, usar *Workspace → Create → Git folder*.
   - **CLI:** `databricks workspace import-dir setup /Workspace/Users/<tu-usuario>/TallerLaTinka/setup` y lo mismo para `app`.
2. Abrir `setup/00_setup_taller` y conectarlo a **Serverless**.
3. Llenar los tres campos de arriba: `catalogo`, `esquema` y `grupo_participantes`. El cuarto campo, `fecha_taller`, ya viene con 2026-11-26.
4. Hacer clic en **Run all**. Tarda unos 6 minutos.
5. Al final el notebook muestra las URLs de Genie, del dashboard y de la app, junto con las tarjetas del Lab 1 con sus valores reales.

El notebook se puede correr varias veces: no duplica nada. **Ojo:** cada corrida vacía el marcador del reto de la app.

### Qué crea

| Recurso | Nombre | Quién accede |
|---|---|---|
| Esquema y tablas | `<catalogo>.<esquema>`: incidencias, proyectos, encuestas_satisfaccion, equipos, incidencias_sla (vista), encuestas_sentimiento | El grupo tiene SELECT. Las tablas del reto (`reto_*`) solo las ve la app |
| SQL Warehouse | `Taller La Tinka` (serverless, 2X-Small, 1–2 clusters, se apaga a los 15 min) | El grupo tiene CAN USE |
| Espacio de Genie | `Mesa de servicio` | El grupo tiene CAN RUN |
| Dashboard | `Mesa de servicio – Seguimiento` (publicado) | El grupo tiene CAN RUN |
| App | `laboratorio-ia-tinka` | El grupo tiene CAN USE. Su service principal recibe permisos mínimos |

Todo queda en la carpeta `Taller La Tinka` del usuario que corrió el setup. Los identificadores se guardan en la tabla `taller_config`.

### Después del taller

Corre `setup/99_limpieza` y escribe `BORRAR` en el campo de confirmación. Elimina la app, el dashboard, Genie, el warehouse y el esquema. El catálogo solo se borra si lo creó el setup.
