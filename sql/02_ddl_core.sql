-- ============================================================================
--  DDL de la base ENTREGADA (secciones 1 a 4 de docs/modelo.dbml)
--  Las secciones 5, 6 y 7 del DBML no están aquí: te corresponde escribirlas
--  en sql/05_ddl_app.sql y sql/06_analytics.sql
-- ============================================================================

-- ---------------------------------------------------------------- etl
CREATE TABLE IF NOT EXISTS etl.ejecucion (
    id_ejecucion      BIGSERIAL PRIMARY KEY,
    flujo             VARCHAR(80)  NOT NULL,
    parametros        JSONB,
    estado            VARCHAR(20)  NOT NULL
                      CHECK (estado IN ('EN_CURSO', 'EXITO', 'FALLO')),
    filas_leidas      INTEGER      NOT NULL DEFAULT 0,
    filas_cargadas    INTEGER      NOT NULL DEFAULT 0,
    filas_rechazadas  INTEGER      NOT NULL DEFAULT 0,
    mensaje_error     TEXT,
    iniciado_en       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    finalizado_en     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_etl_ejecucion_flujo
    ON etl.ejecucion (flujo, iniciado_en DESC);

CREATE TABLE IF NOT EXISTS etl.watermark (
    flujo           VARCHAR(80) PRIMARY KEY,
    valor           VARCHAR(60) NOT NULL,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS etl.rechazo (
    id_rechazo    BIGSERIAL PRIMARY KEY,
    id_ejecucion  BIGINT       NOT NULL REFERENCES etl.ejecucion (id_ejecucion),
    flujo         VARCHAR(80)  NOT NULL,
    regla         VARCHAR(120) NOT NULL,
    payload       JSONB        NOT NULL,
    detectado_en  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_etl_rechazo_flujo
    ON etl.rechazo (flujo, detectado_en DESC);

CREATE TABLE IF NOT EXISTS etl.archivo_procesado (
    id_archivo      BIGSERIAL PRIMARY KEY,
    flujo           VARCHAR(80)  NOT NULL,
    nombre_archivo  VARCHAR(255) NOT NULL,
    hash_contenido  CHAR(64)     NOT NULL,
    filas           INTEGER,
    procesado_en    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ux_archivo_procesado UNIQUE (flujo, nombre_archivo)
);

-- ---------------------------------------------------------------- raw
CREATE TABLE IF NOT EXISTS raw.stg_venta (
    id_carga       BIGSERIAL PRIMARY KEY,
    archivo_origen VARCHAR(255) NOT NULL,
    linea_archivo  INTEGER,
    payload        JSONB        NOT NULL,
    fecha_carga    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.stg_inventario (
    id_carga       BIGSERIAL PRIMARY KEY,
    archivo_origen VARCHAR(255) NOT NULL,
    linea_archivo  INTEGER,
    payload        JSONB        NOT NULL,
    fecha_carga    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- core: dims
CREATE TABLE IF NOT EXISTS core.dim_fecha (
    sk_fecha        INTEGER     PRIMARY KEY,
    fecha           DATE        NOT NULL UNIQUE,
    anio            SMALLINT    NOT NULL,
    trimestre       SMALLINT    NOT NULL,
    mes             SMALLINT    NOT NULL,
    nombre_mes      VARCHAR(20) NOT NULL,
    dia             SMALLINT    NOT NULL,
    dia_semana      SMALLINT    NOT NULL,
    nombre_dia      VARCHAR(20) NOT NULL,
    semana_iso      SMALLINT    NOT NULL,
    es_fin_semana   BOOLEAN     NOT NULL,
    primer_dia_mes  DATE        NOT NULL,
    ultimo_dia_mes  DATE        NOT NULL
);

CREATE TABLE IF NOT EXISTS core.dim_articulo (
    sk_articulo       BIGSERIAL PRIMARY KEY,
    codigo_articulo   VARCHAR(30)  NOT NULL,
    descripcion       VARCHAR(200),
    codigo_categoria  VARCHAR(10),
    categoria         VARCHAR(60),
    subcategoria      VARCHAR(60),
    marca             VARCHAR(60),
    unidad_medida     VARCHAR(10),
    costo_estandar    NUMERIC(14,4) CHECK (costo_estandar >= 0),
    precio_lista      NUMERIC(14,4) CHECK (precio_lista >= 0),
    en_modelo         BOOLEAN      NOT NULL DEFAULT FALSE,
    activo            BOOLEAN      NOT NULL DEFAULT TRUE,
    valido_desde      TIMESTAMPTZ  NOT NULL,
    valido_hasta      TIMESTAMPTZ,
    es_vigente        BOOLEAN      NOT NULL DEFAULT TRUE,
    hash_atributos    CHAR(32),
    fecha_carga       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ux_dim_articulo_version UNIQUE (codigo_articulo, valido_desde),
    CONSTRAINT ck_dim_articulo_vigencia
        CHECK (valido_hasta IS NULL OR valido_hasta > valido_desde)
);
CREATE INDEX IF NOT EXISTS ix_dim_articulo_codigo
    ON core.dim_articulo (codigo_articulo);
CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_articulo_vigente
    ON core.dim_articulo (codigo_articulo) WHERE es_vigente;

CREATE TABLE IF NOT EXISTS core.dim_tienda (
    sk_tienda               BIGSERIAL PRIMARY KEY,
    codigo_tienda           VARCHAR(20)  NOT NULL,
    nombre_tienda           VARCHAR(150),
    departamento            VARCHAR(60),
    region                  VARCHAR(60),
    formato                 VARCHAR(30),
    es_centro_distribucion  BOOLEAN      NOT NULL DEFAULT FALSE,
    activa_modelo           BOOLEAN      NOT NULL DEFAULT FALSE,
    metros_cuadrados        INTEGER,
    fecha_apertura          DATE,
    valido_desde            TIMESTAMPTZ  NOT NULL,
    valido_hasta            TIMESTAMPTZ,
    es_vigente              BOOLEAN      NOT NULL DEFAULT TRUE,
    hash_atributos          CHAR(32),
    fecha_carga             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ux_dim_tienda_version UNIQUE (codigo_tienda, valido_desde),
    CONSTRAINT ck_dim_tienda_vigencia
        CHECK (valido_hasta IS NULL OR valido_hasta > valido_desde)
);
CREATE INDEX IF NOT EXISTS ix_dim_tienda_codigo
    ON core.dim_tienda (codigo_tienda);
CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_tienda_vigente
    ON core.dim_tienda (codigo_tienda) WHERE es_vigente;

-- ---------------------------------------------------------------- core: hechos
CREATE TABLE IF NOT EXISTS core.fct_venta (
    sk_venta             BIGSERIAL,
    id_transaccion       VARCHAR(40)   NOT NULL,
    linea                SMALLINT      NOT NULL,
    sk_fecha             INTEGER       NOT NULL REFERENCES core.dim_fecha (sk_fecha),
    fecha_hora           TIMESTAMPTZ   NOT NULL,
    sk_tienda            BIGINT        NOT NULL REFERENCES core.dim_tienda (sk_tienda),
    sk_articulo          BIGINT        NOT NULL REFERENCES core.dim_articulo (sk_articulo),
    unidades             NUMERIC(14,3) NOT NULL,
    precio_unitario      NUMERIC(14,4),
    descuento            NUMERIC(14,4) NOT NULL DEFAULT 0,
    costo_unitario       NUMERIC(14,4),
    venta_neta           NUMERIC(16,4),
    costo_total          NUMERIC(16,4),
    estado               VARCHAR(20)   NOT NULL
                         CHECK (estado IN ('CONFIRMADA', 'ANULADA', 'DEVOLUCION')),
    canal                VARCHAR(20),
    fecha_actualizacion  TIMESTAMPTZ   NOT NULL,
    fecha_carga          TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT pk_fct_venta PRIMARY KEY (sk_venta),
    CONSTRAINT ux_fct_venta_natural UNIQUE (id_transaccion, linea)
);
CREATE INDEX IF NOT EXISTS ix_fct_venta_fecha_tienda
    ON core.fct_venta (sk_fecha, sk_tienda);
CREATE INDEX IF NOT EXISTS ix_fct_venta_articulo
    ON core.fct_venta (sk_articulo, sk_fecha);
CREATE INDEX IF NOT EXISTS ix_fct_venta_actualizacion
    ON core.fct_venta (fecha_actualizacion);

-- Inventario diario: particionado por rango de sk_fecha (una partición por año)
CREATE TABLE IF NOT EXISTS core.fct_inventario_diario (
    sk_fecha                INTEGER       NOT NULL REFERENCES core.dim_fecha (sk_fecha),
    sk_tienda               BIGINT        NOT NULL REFERENCES core.dim_tienda (sk_tienda),
    sk_articulo             BIGINT        NOT NULL REFERENCES core.dim_articulo (sk_articulo),
    unidades_disponibles    NUMERIC(14,3),
    unidades_transito       NUMERIC(14,3) NOT NULL DEFAULT 0,
    unidades_comprometidas  NUMERIC(14,3) NOT NULL DEFAULT 0,
    costo_promedio          NUMERIC(14,4),
    valor_inventario        NUMERIC(16,4),
    hora_snapshot           TIME,
    fecha_actualizacion     TIMESTAMPTZ,
    fecha_carga             TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT pk_fct_inventario_diario PRIMARY KEY (sk_fecha, sk_tienda, sk_articulo)
) PARTITION BY RANGE (sk_fecha);

CREATE TABLE IF NOT EXISTS core.fct_inventario_diario_2025
    PARTITION OF core.fct_inventario_diario FOR VALUES FROM (20250101) TO (20260101);
CREATE TABLE IF NOT EXISTS core.fct_inventario_diario_2026
    PARTITION OF core.fct_inventario_diario FOR VALUES FROM (20260101) TO (20270101);
-- TODO (candidato): la data histórica arranca en 2025-03. Si tu carga cubre
-- fechas fuera de estos rangos, agrega las particiones que falten. Considera
-- si conviene automatizar su creación desde el ETL.

CREATE INDEX IF NOT EXISTS ix_fct_inv_diario_articulo
    ON core.fct_inventario_diario (sk_articulo, sk_fecha);

CREATE TABLE IF NOT EXISTS core.fct_inventario_intradia (
    sk_fecha                INTEGER       NOT NULL REFERENCES core.dim_fecha (sk_fecha),
    hora_snapshot           TIME          NOT NULL,
    sk_tienda               BIGINT        NOT NULL REFERENCES core.dim_tienda (sk_tienda),
    sk_articulo             BIGINT        NOT NULL REFERENCES core.dim_articulo (sk_articulo),
    unidades_disponibles    NUMERIC(14,3),
    unidades_transito       NUMERIC(14,3) NOT NULL DEFAULT 0,
    unidades_comprometidas  NUMERIC(14,3) NOT NULL DEFAULT 0,
    costo_promedio          NUMERIC(14,4),
    fecha_actualizacion     TIMESTAMPTZ,
    fecha_carga             TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT pk_fct_inventario_intradia
        PRIMARY KEY (sk_fecha, hora_snapshot, sk_tienda, sk_articulo)
);
