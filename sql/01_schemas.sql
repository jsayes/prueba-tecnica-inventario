-- ============================================================================
--  Capas del modelo
--   raw       : aterrizaje de las fuentes, sin transformar
--   core      : modelo dimensional (dimensiones y hechos)
--   analytics : objetos de consumo para la aplicación  [a completar]
--   app       : entidades transaccionales de la aplicación  [a completar]
--   etl       : control de ejecuciones, watermarks y rechazos
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS etl;
