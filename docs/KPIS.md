# KPIs y capa de consumo

> Plantilla a completar por el candidato. La capa `analytics` se entrega vacía: su arquitectura es tu entregable.

## 1. Arquitectura de la capa

- **Estructura propuesta** (qué objetos existen y de qué tipo):
- **Por qué esta estructura y no otra**, dado el patrón de consumo del dashboard:
- **Qué sacrifico** con esta decisión:
- **Cómo se mantiene actualizada** y quién dispara el refresco:
- **Cómo encaja con la orquestación** que implementaste:

## 2. Definición de los KPIs

| KPI | Fórmula sobre el modelo | Grano | Objeto que lo resuelve | Implementado |
|---|---|---|---|---|
| Ventas mensuales | | | | sí / no |
| Costo de inventario | | | | |
| Margen | | | | |
| Rotación | | | | |
| GMROI | | | | |
| Stockouts | | | | |

## 3. Decisiones sobre el cálculo

- ¿Qué excluyes del cálculo de ventas: anuladas, devoluciones, ambas? ¿Por qué?
- ¿El inventario promedio del periodo lo calculas como promedio de snapshots diarios o como (inicial + final) / 2? ¿Qué implica cada opción?
- ¿Cómo defines un stockout y en qué unidad lo cuentas: eventos, días-artículo-tienda, porcentaje del surtido?
- Rotación y GMROI son razones. ¿Qué pasa cuando el dashboard agrega de artículo a categoría, o de tienda a región? ¿Tu estructura lo resuelve o el frontend tiene que recalcular?
- ¿Restringes los KPIs a artículos con `en_modelo = true` y tiendas con `activa_modelo = true`? ¿Los KPIs históricos usan la bandera vigente hoy o la vigente en su momento?
- Las dimensiones son SCD 2. ¿Con qué versión del costo calculas el margen de una venta antigua?
- ¿Qué haces con los artículos que tienen ventas pero no inventario en el periodo, y con los de inventario cero?

## 4. Consultas

Las implementaciones quedan en `sql/06_analytics.sql`.
