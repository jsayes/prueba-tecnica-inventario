# Decisiones y supuestos

> Plantilla a completar por el candidato. Con 4 horas de presupuesto, esta bitácora pesa tanto como el código.

## 1. Supuestos

| # | Supuesto | Motivo |
| 1 | Hora de negocio = America/Guatemala (UTC−6, sin horario de verano). | Los schedules y las fechas de los flujos dependen de ella; el contenedor corre en UTC. |
| 2 | Los cortes de ventas llegan ~10 min después de la hora nominal (08:00, 14:00, 20:00). | Los flujos se lanzan a :10 y reintentan 3 veces cada 5 min. |
| 3 | El inventario intradía se publica 06:00–23:30 cada 30 min; el cierre corre a las 00:30 y cierra **ayer**. | El último snapshot del día es el de las 23:30. |
| 4 | Un snapshot completo tiene ≈ las filas del cierre del día anterior (tolerancia 95 %); sin cierre previo se usan 1080 filas (fallback configurable). | Es el único dato disponible para saber cuántas filas «deberían» llegar. |
| 5 | `fecha_actualizacion` mayor = versión más reciente; con empate gana la entrante (el `WHERE ... <=` lo permite sin cambiar datos). | Lo indica el enunciado. |
| 6 | Los KPIs miden el negocio completo: no filtran por `en_modelo` / `activa_modelo`. | Las banderas definen el alcance del modelo de IA, no del negocio. |
| 7 | Los centros de distribución no cuentan para stockouts. | No venden al público. |

## 2. Decisiones técnicas

Las tres que el evaluador va a buscar sí o sí:

| # | Decisión | Alternativas | Motivo |
| 1 | **Ventas que llegan tarde:** se asignan al `sk_fecha` de su `fecha_hora` **real** (no al día del corte). Implica que el KPI del día anterior se **restatea**: las ventas de ayer pueden crecer al llegar un corte de hoy. Verificado: 20 filas del corte del 03/03 14:00 modificaron el 02/03. El refresco de la MV de ventas del mismo flujo propaga el cambio. | Asignar al día del corte (el pasado queda estable, pero el día de hoy se infla y el de ayer queda subestimado para siempre; margen y rotación por día pierden sentido). | La fecha de negocio es cuándo ocurrió la venta. Un KPI debe ser **correcto**, no sólo estable; la restatement es acotada (pocas filas, días recientes) y se documenta. Costo: un reporte ya publicado puede cambiar. |
| 2 | **Snapshot incompleto:** se **descarta entero**; la ejecución queda FALLIDA con `SnapshotIncompleto` (p. ej. `648/1077 filas`), sin reintentos y con alerta. Se evalúa **después** de deduplicar (para que un snapshot con duplicados no parezca completo ni uno completo con repetidos parezca más largo). | Cargar parcial (un inventario con huecos parece stock cero y dispara falsos stockouts y mala rotación); marcar como degradado y cargar (los consumidores no miran la marca). | Un dato ausente es mejor que un dato falso. Como cada snapshot es independiente y llega otro en 30 min, el costo es bajo. El cierre usa el último snapshot **válido**. El esperado es 1077, no 1080, porque se deriva del cierre previo, que ya excluyó filas rechazadas. |
| 3 | **Unidades disponibles negativas:** se **rechazan** a cuarentena, no se truncan a 0. | Truncar a 0. | Truncar fabrica un stockout que quizá no existe y esconde un error del origen (conteo, devolución sin registrar). La cuarentena lo hace visible sin contaminar el KPI. |
| 4 | **Upsert:** una sentencia por fila con `ON CONFLICT DO UPDATE ... WHERE existente <= entrante AND (cols) IS DISTINCT FROM (...)`; el lote se resuelve antes en Python (gana la mayor `fecha_actualizacion`). | Staging + `MERGE`; ejecutar en bloque con `executemany`. | Idempotente e independiente del orden de llegada; el `IS DISTINCT FROM` evita escrituras inútiles, y `rowcount` exacto permite probar idempotencia (rerun = 0). Costo: una ida a la BD por fila (aceptable con ~miles de filas por corte). |
| 5 | **Snapshot:** `SnapshotLoader` reemplaza el alcance `(sk_fecha, hora_snapshot)`. | Upsert por llave. | Un snapshot es una foto completa: filas que ya no vienen deben desaparecer; y el reproceso no deja residuos. |
| 6 | **Cierre diario en SQL**, `ON CONFLICT DO UPDATE`, con creación de la partición anual si falta. Falla si no hay snapshots. | Cierre en Python; no crear particiones. | Lo pide el enunciado (paso SQL idempotente); las particiones entregadas no cubren el rango y fallar tarde sería peor. |
| 7 | **Capa de KPIs:** 2 MV aditivas (mes × tienda × artículo) + vistas; razones como cociente de sumas; atributos por código vigente. | Ver `docs/MODELO.md` §2. | — |
| 8 | **Instrucciones:** auditoría por campo, propuesta original inmutable, `sk_*`, una vigente por índice único parcial. | Ver `docs/MODELO.md` §1. | — |
| 9 | **Prefect 3.9.4** en lugar de 3.0.0; **`tzdata`** añadido. | Fijar versiones antiguas de pydantic/fastapi. | 3.0.0 falla al importar con pydantic/fastapi actuales (`BaseResult`, `Body(min_items)`); `tzdata` garantiza `ZoneInfo` en imágenes mínimas. |
| 10 | `psycopg[binary]==3.1.18` se mantiene. | Subir versión. | La imagen Docker usa Python 3.12.

## 3. Fuera de alcance

| # | Pendiente | Cómo lo abordaría |
|---|---|---|
| 1 | Alerta real (Slack/correo) | hoy es log de error. |
| 2 | Alerta por ratio de rechazo sobre un máximo | Umbral en `config.yaml` evaluado en `Pipeline`, que falle la ejecución al superarlo. |
| 3 | Refresco incremental de las MV | Tablas físicas con recálculo sólo del mes abierto si el refresco total deja de caber en la ventana. |
| 4 | Inventario intradía en los KPIs | Vista sobre el último snapshot del día para un tablero operativo; los KPIs mensuales usan el cierre. |
| 5 | Pruebas de integración en CI | GitHub Actions con servicio PostgreSQL 16 que corra `pytest` y los SQL. |
| 6 | Prueba end-to-end con `docker compose` | Verifiqué contra un PostgreSQL 16 local 

