# KPIs y capa de consumo

> Plantilla a completar por el candidato. La capa `analytics` se entrega vacía: su arquitectura es tu entregable.

## 1. Arquitectura de la capa

- **Estructura propuesta** (qué objetos existen y de qué tipo):
Son siete objetos en el schema analytics.


- **Por qué esta estructura y no otra**, dado el patrón de consumo del dashboard:
El patrón es mucha lectura con filtros por atributos; se materializa lo caro a un grano que contiene todos los filtros y las razones se calculan al final sobre sumas.

- **Qué sacrifico** con esta decisión:
Latencia del dato (3 veces al día ventas, 1 inventario), refresco completo del histórico, atributos vigentes aplicados a toda la historia.

- **Cómo se mantiene actualizada** y quién dispara el refresco:
función `analytics.refrescar(p_ventas, p_inventario)`; la dispara la orquestación: `flujo_ventas` (sólo ventas) tras cada corte, `flujo_cierre` (ambas) tras el cierre y `flujo_refresco_kpis` a las 00:45 como red de seguridad. Manual: `python main.py refrescar-kpis`

- **Cómo encaja con la orquestación** que implementaste:


## 2. Definición de los KPIs

| KPI | Fórmula sobre el modelo | Grano | Objeto que lo resuelve | Implementado |
|---|---|---|---|---|
| Ventas mensuales | `SUM(venta_neta)` (CONFIRMADA + DEVOLUCION; sin ANULADA) | mes × región × formato × categoría × subcategoría | `mv_ventas_mes` → `v_kpi_mensual.ventas_mensuales` | sí |
| Costo de inventario | `SUM(valor_cierre_mes)` (cierre del mes) y `SUM(inv_promedio_mes)` (promedio de cierres diarios) | ídem | `mv_inventario_mes` → `costo_inventario_cierre`, `costo_inventario_promedio` | sí |
| Margen | bruto = `SUM(venta_neta) − SUM(costo_venta)`; % = bruto / `SUM(venta_neta)` | ídem | `mv_ventas_mes` → `margen_bruto`, `margen_pct` | sí |
| Rotación | `SUM(costo_venta) / SUM(inv_promedio_mes)` (del mes; para un periodo, ver §4) | ídem | `v_kpi_mensual.rotacion_mes` | sí |
| GMROI | `(SUM(venta_neta) − SUM(costo_venta)) / SUM(inv_promedio_mes)` | ídem | `v_kpi_mensual.gmroi_mes` | sí |
| Stockouts | `SUM(dias_stockout)` y tasa = días con `unidades_disponibles ≤ 0` / días-artículo-tienda observados | ídem | `mv_inventario_mes` → `dias_stockout`, `tasa_stockout` | sí |

## 3. Decisiones sobre el cálculo

- ¿Qué excluyes del cálculo de ventas: anuladas, devoluciones, ambas? ¿Por qué?
entran CONFIRMADA y DEVOLUCION (la devolución llega negativa y reduce la venta neta); se excluye ANULADA porque no ocurrió.

- ¿El inventario promedio del periodo lo calculas como promedio de snapshots diarios o como (inicial + final) / 2? ¿Qué implica cada opción?
promedio de los **cierres diarios** del mes (no (inicial+final)/2): sigue picos y quiebres dentro del mes. Costo: depende de que existan los 28–31 cierres

- ¿Cómo defines un stockout y en qué unidad lo cuentas: eventos, días-artículo-tienda, porcentaje del surtido?
con `unidades_disponibles ≤ 0`; la tasa lo divide por días observados. Se excluyen centros de distribución (no venden al público). Cuenta días, no eventos, y es una unidad aditiva.

- Rotación y GMROI son razones. ¿Qué pasa cuando el dashboard agrega de artículo a categoría, o de tienda a región? ¿Tu estructura lo resuelve o el frontend tiene que recalcular?
se calculan siempre como **cociente de sumas** del nivel consultado; el frontend no recalcula ni promedia. `rotacion_mes` y `gmroi_mes` son mensuales: no se anualizan.

- ¿Restringes los KPIs a artículos con `en_modelo = true` y tiendas con `activa_modelo = true`? ¿Los KPIs históricos usan la bandera vigente hoy o la vigente en su momento?
- Las dimensiones son SCD 2. ¿Con qué versión del costo calculas el margen de una venta antigua?
los KPIs **no** filtran por ellas (miden el negocio, no el alcance del modelo); `v_dim_*_actual` las expone para que el dashboard filtre si lo desea.


- ¿Qué haces con los artículos que tienen ventas pero no inventario en el periodo, y con los de inventario cero?
El costo viene del hecho (`costo_total`), es decir el de la versión vigente cuando ocurrió la venta. Los atributos de agrupación son los de hoy.

## 4. Consultas

Las implementaciones quedan en `sql/06_analytics.sql`.
SELECT region, ventas_mensuales, margen_pct, rotacion_mes, gmroi_mes, tasa_stockout
  FROM analytics.v_kpi_mensual
 WHERE mes = '2026-03-01' AND formato = 'Super' ORDER BY region;

-- Periodo de varios meses: sumar numeradores y denominadores, NO promediar razones
SELECT region,
       SUM(ventas_mensuales)                         AS ventas,
       SUM(costo_inventario_promedio)                AS inv_prom_acumulado,
       (SUM(margen_bruto)) / NULLIF(SUM(costo_inventario_promedio), 0) AS gmroi_periodo
  FROM analytics.v_kpi_mensual
 WHERE mes BETWEEN '2025-03-01' AND '2025-05-01'
 GROUP BY region;