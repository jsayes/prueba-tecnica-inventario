-- ============================================================================
--  Schema analytics — TU ENTREGABLE
--
--  Capa de consumo de los KPIs: ventas mensuales, costo de inventario,
--  margen, rotación, GMROI y stockouts.
--
--  Aquí no hay nada resuelto: la arquitectura de esta capa es tuya. El
--  contexto para decidirla está en docs/modelo.dbml, sección 7.
--
--  Se evalúa, en este orden:
--    1. la arquitectura que propones y su justificación (docs/MODELO.md);
--    2. la definición de cada KPI: fórmula y grano (docs/KPIS.md);
--    3. la implementación: al menos 3 de los 6 KPIs de punta a punta aquí.
--
--  Este archivo se aplica a mano, después de cargar datos:
--    psql "postgresql://etl_user:cambiame@localhost:5432/inventario_db" \
--         -f sql/06_analytics.sql
-- ============================================================================

CREATE OR REPLACE VIEW analytics.v_dim_articulo_actual AS
SELECT codigo_articulo, descripcion, categoria, subcategoria, marca, en_modelo
  FROM core.dim_articulo
 WHERE es_vigente;

CREATE OR REPLACE VIEW analytics.v_dim_tienda_actual AS
SELECT codigo_tienda, nombre_tienda, region, formato, es_centro_distribucion, activa_modelo
  FROM core.dim_tienda
 WHERE es_vigente;

-- Ventas: CONFIRMADA y DEVOLUCION entran (la devolución es negativa); ANULADA no.
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_ventas_mes AS
SELECT f.primer_dia_mes   AS mes,
       t.codigo_tienda,
       a.codigo_articulo,
       SUM(v.unidades)    AS unidades,
       SUM(v.venta_neta)  AS venta_neta,
       SUM(v.costo_total) AS costo_venta,
       COUNT(*)           AS lineas
  FROM core.fct_venta v
  JOIN core.dim_fecha    f ON f.sk_fecha    = v.sk_fecha
  JOIN core.dim_tienda   t ON t.sk_tienda   = v.sk_tienda
  JOIN core.dim_articulo a ON a.sk_articulo = v.sk_articulo
 WHERE v.estado IN ('CONFIRMADA', 'DEVOLUCION')
 GROUP BY f.primer_dia_mes, t.codigo_tienda, a.codigo_articulo
WITH DATA;
-- Índice ÚNICO: requisito de REFRESH ... CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_ventas_mes
    ON analytics.mv_ventas_mes (mes, codigo_tienda, codigo_articulo);

-- Inventario: desde el CIERRE diario.
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_inventario_mes AS
SELECT f.primer_dia_mes AS mes,
       t.codigo_tienda,
       a.codigo_articulo,
       AVG(i.valor_inventario)                                    AS inv_promedio_mes,
       (ARRAY_AGG(i.valor_inventario ORDER BY f.fecha DESC))[1]   AS valor_cierre_mes,
       COUNT(*) FILTER (WHERE i.unidades_disponibles <= 0)        AS dias_stockout,
       COUNT(*)                                                   AS dias_observados
  FROM core.fct_inventario_diario i
  JOIN core.dim_fecha    f ON f.sk_fecha    = i.sk_fecha
  JOIN core.dim_tienda   t ON t.sk_tienda   = i.sk_tienda
  JOIN core.dim_articulo a ON a.sk_articulo = i.sk_articulo
 GROUP BY f.primer_dia_mes, t.codigo_tienda, a.codigo_articulo
WITH DATA;
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_inventario_mes
    ON analytics.mv_inventario_mes (mes, codigo_tienda, codigo_articulo);

CREATE OR REPLACE VIEW analytics.v_cubo_kpi_mes AS
SELECT mes, codigo_tienda, codigo_articulo,
       t.region, t.formato, t.es_centro_distribucion,
       a.categoria, a.subcategoria,
       COALESCE(v.unidades, 0)         AS unidades,
       COALESCE(v.venta_neta, 0)       AS venta_neta,
       COALESCE(v.costo_venta, 0)      AS costo_venta,
       COALESCE(i.inv_promedio_mes, 0) AS inv_promedio_mes,
       COALESCE(i.valor_cierre_mes, 0) AS valor_cierre_mes,
       COALESCE(i.dias_stockout, 0)    AS dias_stockout,
       COALESCE(i.dias_observados, 0)  AS dias_observados
  FROM analytics.mv_ventas_mes v
  FULL JOIN analytics.mv_inventario_mes i USING (mes, codigo_tienda, codigo_articulo)
  LEFT JOIN analytics.v_dim_tienda_actual   t USING (codigo_tienda)
  LEFT JOIN analytics.v_dim_articulo_actual a USING (codigo_articulo);

-- Los 6 KPIs. Razones = cociente de sumas; nunca promedio de razones.
-- Stockouts excluye centros de distribución (no venden al público).
CREATE OR REPLACE VIEW analytics.v_kpi_mensual AS
SELECT mes, region, formato, categoria, subcategoria,
       SUM(venta_neta)                                               AS ventas_mensuales,
       SUM(valor_cierre_mes)                                         AS costo_inventario_cierre,
       SUM(inv_promedio_mes)                                         AS costo_inventario_promedio,
       SUM(venta_neta) - SUM(costo_venta)                            AS margen_bruto,
       (SUM(venta_neta) - SUM(costo_venta)) / NULLIF(SUM(venta_neta), 0)        AS margen_pct,
       SUM(costo_venta) / NULLIF(SUM(inv_promedio_mes), 0)                      AS rotacion_mes,
       (SUM(venta_neta) - SUM(costo_venta)) / NULLIF(SUM(inv_promedio_mes), 0)  AS gmroi_mes,
       SUM(dias_stockout) FILTER (WHERE NOT COALESCE(es_centro_distribucion, FALSE)) AS dias_stockout,
       (SUM(dias_stockout) FILTER (WHERE NOT COALESCE(es_centro_distribucion, FALSE)))::numeric
         / NULLIF(SUM(dias_observados) FILTER (WHERE NOT COALESCE(es_centro_distribucion, FALSE)), 0)
                                                                     AS tasa_stockout
  FROM analytics.v_cubo_kpi_mes
 GROUP BY mes, region, formato, categoria, subcategoria;

-- Refresco: lo invoca la orquestación (flujo_ventas tras cada corte; flujo_cierre tras el cierre).
CREATE OR REPLACE FUNCTION analytics.refrescar(p_ventas BOOLEAN DEFAULT TRUE,
                                               p_inventario BOOLEAN DEFAULT TRUE)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    IF p_ventas THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_ventas_mes;
    END IF;
    IF p_inventario THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_inventario_mes;
    END IF;
END $$;

