# ETL — Aplicación de inventario óptimo

Repositorio base de la prueba técnica para **Ingeniero de Datos (mid level)**.
Enunciado y criterios de evaluación: [`ENUNCIADO.md`](ENUNCIADO.md). Esfuerzo esperado: **≈ 4 horas**.

## Qué ya está implementado y qué te toca

| Componente | Estado |
|---|---|
| Schemas, DDL de `raw`, `core` y `etl`, seed de `dim_fecha` | ✅ Entregado |
| DDL de `app`: usuarios, refresh tokens, módulos, permisos y su asignación | ✅ Entregado |
| `CSVExtractor`, cleaners, transformer configurable, deduplicador | ✅ Entregado |
| `VentaTransformer`, `InventarioTransformer`, `DimensionResolver` (llaves surrogadas y medidas) | ✅ Entregado |
| `SCD2Loader` + flujos `dim_articulo` y `dim_tienda` | ✅ Entregado |
| `FullOnceLoader` + flujos `ventas_historico` e `inventario_historico` | ✅ Entregado |
| `Pipeline` con registro en `etl.ejecucion`, rechazos y métricas | ✅ Entregado |
| Reglas de calidad de ventas | ✅ Entregado |
| Docker Compose de PostgreSQL, ETL y Prefect (servidor + worker) con `flujo_catalogos` desplegado | ✅ Entregado |
| **`UpsertLoader` + `ventas_intradia`** | ⬜ Tu entregable |
| **`inventario_intradia` + `cerrar_inventario_dia` + `REGLAS_INVENTARIO`** | ⬜ Tu entregable |
| **Flujos y schedules de ventas, inventario y cierre** | ⬜ Tu entregable |
| **Sección 6 del modelo: instrucciones y auditoría de ediciones** | ⬜ Tu entregable |
| **Sección 7 del modelo: arquitectura completa de la capa de KPIs** | ⬜ Tu entregable |
| **2 pruebas unitarias** | ⬜ Tu entregable |

## Estructura

```
.
├── ENUNCIADO.md                    # qué se pide y cómo se evalúa
├── DECISIONES.md                   # (a completar)
├── data/
│   ├── catalogos/                  # snapshots diarios de artículos y tiendas
│   ├── ventas/historico/           # 3 años, carga única
│   ├── ventas/intradia/            # 3 cortes por día  <- tu entregable
│   ├── inventario/historico/       # 1 año de cierres diarios
│   └── inventario/intradia/        # snapshots cada 30 min  <- tu entregable
├── docs/
│   ├── modelo.dbml                 # secciones 1-5 listas; 6 y 7 por completar
│   ├── BASE_DE_DATOS.md            # DER y diccionario de datos
│   ├── MODELO.md                   # (a completar)
│   ├── KPIS.md                     # (a completar)
│   └── ORQUESTACION.md             # (a completar)
├── sql/
│   ├── 01_schemas.sql              # entregado
│   ├── 02_ddl_core.sql             # entregado
│   ├── 03_seed_dim_fecha.sql       # entregado
│   ├── 05_ddl_app.sql              # auth y permisos entregados; instrucciones por completar
│   └── 06_analytics.sql            # vacío: la capa de KPIs es tu entregable
├── src/
│   ├── config/                     # settings + config.yaml
│   ├── extractors/                 # CSVExtractor
│   ├── transformers/               # cleaners, generic, facts
│   ├── loaders/                    # SCD2Loader, FullOnceLoader, UpsertLoader (TODO)
│   ├── quality/                    # motor + reglas de ventas
│   ├── pipelines/                  # dimensiones, ventas, inventario
│   └── utils/                      # logger, db, run_tracker
├── orchestration/
│   ├── flows/etl_flows.py          # flujo_catalogos implementado; el resto TODO
│   ├── prefect.yaml                # despliegue de catálogos listo
│   └── dags/                       # alternativa Airflow
├── tests/
├── main.py                         # CLI del ETL
├── docker-compose.yml              # postgres + etl
├── docker-compose.prefect.yml      # orquestador (opción A, base funcional)
├── docker-compose.airflow.yml      # orquestador (opción B)
└── Dockerfile
```

## Puesta en marcha

### 1. Entorno

```bash
cp .env.example .env          # ajustar credenciales si quieres

python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Base de datos

```bash
docker compose up -d postgres
docker compose logs -f postgres    # esperar "database system is ready to accept connections"
```

Se aplican automáticamente `01_schemas.sql`, `02_ddl_core.sql` y `03_seed_dim_fecha.sql`.

`05_ddl_app.sql` (auth y permisos entregados + tu sección de instrucciones) y `06_analytics.sql` (tu capa de KPIs) se aplican a mano:

```bash
export DB="postgresql://etl_user:cambiame@localhost:5432/inventario_db"
psql "$DB" -f sql/05_ddl_app.sql
psql "$DB" -f sql/06_analytics.sql     # después de cargar datos
```

### 3. Dimensiones (ya funciona)

```bash
python main.py dim-articulo --fecha-archivo 20260301
python main.py dim-tienda   --fecha-archivo 20260301

# el snapshot del día siguiente trae cambios: debe versionar, no duplicar
python main.py dim-articulo --fecha-archivo 20260302
python main.py dim-tienda   --fecha-archivo 20260302
```

```sql
SELECT codigo_articulo, costo_estandar, valido_desde, valido_hasta, es_vigente
  FROM core.dim_articulo
 WHERE codigo_articulo = 'ART-00001'
 ORDER BY valido_desde;
```

### 4. Cargas históricas (ya funcionan)

Reejecutarlas no duplica: el archivo queda registrado en `etl.archivo_procesado`.

```bash
for a in 2023 2024 2025 2026; do python main.py ventas-historico --anio $a; done
for m in 202503 202504 202505; do python main.py inventario-historico --periodo $m; done
```

> El histórico de inventario cubre desde marzo de 2025. Revisa las particiones de `core.fct_inventario_diario` antes de cargar todos los meses.

### 5. Cargas intradía (tu entregable)

```bash
python main.py ventas-intradia     --fecha 2026-03-02 --corte 0800
python main.py ventas-intradia     --fecha 2026-03-02 --corte 1400
python main.py ventas-intradia     --fecha 2026-03-02 --corte 2000
python main.py inventario-intradia --fecha 2026-03-02 --hora 0630
python main.py cerrar-inventario   --fecha 2026-03-02
```

### 6. Pruebas

```bash
pytest -q
```

### 7. Orquestación

```bash
docker compose -f docker-compose.yml -f docker-compose.prefect.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prefect.yml \
    exec prefect-worker prefect deploy --all
# UI en http://localhost:4200
```

`catalogos-diario` ya queda desplegado. Los demás despliegues están comentados en `orchestration/prefect.yaml`.

## Datos de prueba disponibles

| Carpeta | Archivos | Notas |
|---|---|---|
| `data/catalogos/` | 2 snapshots por catálogo (`20260301`, `20260302`) | El segundo trae cambios de costo, precio y banderas |
| `data/ventas/historico/` | `ventas_2023.csv` … `ventas_2026.csv` | ~170 mil líneas |
| `data/ventas/intradia/` | 2 días × 3 cortes | Acumulados, con anulaciones, correcciones y ventas tardías |
| `data/inventario/historico/` | 12 archivos mensuales | ~394 mil filas |
| `data/inventario/intradia/` | 7 snapshots de 30 min (06:00–09:00) | El de 07:30 está incompleto; el de 08:30 trae duplicados |
