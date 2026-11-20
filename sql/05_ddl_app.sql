-- ============================================================================
--  Schema app
--
--  La sección 5 del DBML (autenticación y autorización por módulo) se entrega
--  IMPLEMENTADA como referencia de estilo y de nivel de detalle esperado.
--
--  La sección 6 (instrucciones del modelo y auditoría de ediciones) es TU
--  ENTREGABLE: escríbela al final de este archivo. Requisitos en
--  docs/modelo.dbml, sección 6.
--
--  Este archivo se aplica a mano:
--    psql "postgresql://etl_user:cambiame@localhost:5432/inventario_db" \
--         -f sql/05_ddl_app.sql
-- ============================================================================

-- ---------------------------------------------------------------------------
--  Sección 5 — ENTREGADA
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.usuario (
    id_usuario            BIGSERIAL PRIMARY KEY,
    usuario               VARCHAR(60)  NOT NULL,
    correo                VARCHAR(150) NOT NULL,
    nombre_completo       VARCHAR(150),
    hash_contrasena       VARCHAR(255) NOT NULL,
    requiere_cambio_pass  BOOLEAN      NOT NULL DEFAULT TRUE,
    activo                BOOLEAN      NOT NULL DEFAULT TRUE,
    ultimo_ingreso_en     TIMESTAMPTZ,
    creado_por            BIGINT       REFERENCES app.usuario (id_usuario),
    creado_en             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ux_usuario_usuario UNIQUE (usuario),
    CONSTRAINT ux_usuario_correo  UNIQUE (correo)
);
COMMENT ON COLUMN app.usuario.requiere_cambio_pass IS
    'El administrador crea el usuario con contraseña temporal; se fuerza el cambio en el primer ingreso.';

CREATE TABLE IF NOT EXISTS app.sesion_token (
    id_token       BIGSERIAL PRIMARY KEY,
    id_usuario     BIGINT       NOT NULL REFERENCES app.usuario (id_usuario) ON DELETE CASCADE,
    hash_refresh   CHAR(64)     NOT NULL,
    emitido_en     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expira_en      TIMESTAMPTZ  NOT NULL,
    revocado_en    TIMESTAMPTZ,
    CONSTRAINT ux_sesion_token_hash UNIQUE (hash_refresh),
    CONSTRAINT ck_sesion_token_vigencia CHECK (expira_en > emitido_en)
);
CREATE INDEX IF NOT EXISTS ix_sesion_token_usuario
    ON app.sesion_token (id_usuario) WHERE revocado_en IS NULL;

CREATE TABLE IF NOT EXISTS app.modulo (
    id_modulo   SMALLSERIAL PRIMARY KEY,
    codigo      VARCHAR(40)  NOT NULL,
    nombre      VARCHAR(80)  NOT NULL,
    activo      BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT ux_modulo_codigo UNIQUE (codigo)
);

CREATE TABLE IF NOT EXISTS app.permiso (
    id_permiso  SMALLSERIAL PRIMARY KEY,
    codigo      VARCHAR(20) NOT NULL,
    nombre      VARCHAR(60) NOT NULL,
    CONSTRAINT ux_permiso_codigo UNIQUE (codigo)
);

CREATE TABLE IF NOT EXISTS app.usuario_modulo_permiso (
    id_usuario   BIGINT      NOT NULL REFERENCES app.usuario (id_usuario) ON DELETE CASCADE,
    id_modulo    SMALLINT    NOT NULL REFERENCES app.modulo (id_modulo),
    id_permiso   SMALLINT    NOT NULL REFERENCES app.permiso (id_permiso),
    otorgado_por BIGINT      REFERENCES app.usuario (id_usuario),
    otorgado_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_usuario_modulo_permiso PRIMARY KEY (id_usuario, id_modulo, id_permiso)
);
COMMENT ON TABLE app.usuario_modulo_permiso IS
    'Asignación usuario x módulo x permiso. La PK compuesta evita duplicados y sirve como índice de la consulta de permisos efectivos.';

INSERT INTO app.modulo (codigo, nombre) VALUES
    ('CATALOGO_ARTICULOS', 'Catálogo de artículos'),
    ('CATALOGO_TIENDAS',   'Catálogo de tiendas'),
    ('INSTRUCCIONES',      'Instrucciones'),
    ('KPIS',               'KPIs')
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO app.permiso (codigo, nombre) VALUES
    ('VER',      'Ver'),
    ('CREAR',    'Crear'),
    ('EDITAR',   'Editar'),
    ('ELIMINAR', 'Eliminar')
ON CONFLICT (codigo) DO NOTHING;

-- ============================================================================
--  Sección 6 — TU ENTREGABLE: instrucciones del modelo y auditoría de
--  ediciones. Requisitos en docs/modelo.dbml, sección 6.
--  La FK del usuario que edita debe apuntar a app.usuario.
-- ============================================================================
CREATE TABLE IF NOT EXISTS app.corrida_modelo (
    id_corrida      BIGSERIAL    PRIMARY KEY,
    ejecutada_en    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    version_modelo  VARCHAR(40)  NOT NULL,
    parametros      JSONB,
    estado          VARCHAR(20)  NOT NULL DEFAULT 'EN_CURSO',
    es_vigente      BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_corrida_estado CHECK (estado IN ('EN_CURSO', 'COMPLETADA', 'FALLIDA')),
    CONSTRAINT ck_corrida_vigente_completa CHECK (NOT es_vigente OR estado = 'COMPLETADA')
);
COMMENT ON TABLE app.corrida_modelo IS
    'Una fila por ejecución periódica del modelo. Solo una puede ser vigente.';
-- UNA sola corrida vigente: todas las filas vigentes colisionan en el mismo valor constante
CREATE UNIQUE INDEX IF NOT EXISTS ux_corrida_vigente
    ON app.corrida_modelo ((TRUE)) WHERE es_vigente;
CREATE INDEX IF NOT EXISTS ix_corrida_ejecutada ON app.corrida_modelo (ejecutada_en DESC);

CREATE TABLE IF NOT EXISTS app.instruccion (
    id_instruccion      BIGSERIAL     PRIMARY KEY,
    id_corrida          BIGINT        NOT NULL REFERENCES app.corrida_modelo (id_corrida),
    sk_articulo         BIGINT        NOT NULL REFERENCES core.dim_articulo (sk_articulo),
    sk_tienda_origen    BIGINT        NOT NULL REFERENCES core.dim_tienda (sk_tienda),
    sk_tienda_destino   BIGINT        NOT NULL REFERENCES core.dim_tienda (sk_tienda),
    unidades_modelo     NUMERIC(14,3) NOT NULL,
    comentario_modelo   TEXT,
    unidades            NUMERIC(14,3) NOT NULL,
    comentario          TEXT,
    estado              VARCHAR(20)   NOT NULL DEFAULT 'PROPUESTA',
    modificado_por      BIGINT        REFERENCES app.usuario (id_usuario),
    modificado_en       TIMESTAMPTZ,
    creado_en           TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT ck_instruccion_estado
        CHECK (estado IN ('PROPUESTA', 'EDITADA', 'APROBADA', 'DESCARTADA', 'EJECUTADA')),
    CONSTRAINT ck_instruccion_origen_destino CHECK (sk_tienda_origen <> sk_tienda_destino),
    CONSTRAINT ck_instruccion_unidades CHECK (unidades_modelo > 0 AND unidades > 0),
    CONSTRAINT ux_instruccion_propuesta
        UNIQUE (id_corrida, sk_articulo, sk_tienda_origen, sk_tienda_destino)
);
COMMENT ON COLUMN app.instruccion.unidades_modelo IS
    'Propuesta ORIGINAL del modelo. Inmutable (trigger): base del indicador de confianza.';
COMMENT ON COLUMN app.instruccion.unidades IS
    'Valor vigente: igual al del modelo hasta que un usuario lo edita.';
CREATE INDEX IF NOT EXISTS ix_instruccion_corrida ON app.instruccion (id_corrida);
CREATE INDEX IF NOT EXISTS ix_instruccion_articulo ON app.instruccion (sk_articulo);

CREATE TABLE IF NOT EXISTS app.instruccion_auditoria (
    id_auditoria    BIGSERIAL    PRIMARY KEY,
    id_instruccion  BIGINT       NOT NULL REFERENCES app.instruccion (id_instruccion),
    campo           VARCHAR(40)  NOT NULL,
    valor_anterior  TEXT,
    valor_nuevo     TEXT,
    id_usuario      BIGINT       NOT NULL REFERENCES app.usuario (id_usuario),
    modificado_en   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_instruccion_auditoria_campo CHECK (campo IN ('unidades', 'comentario', 'estado'))
);
CREATE INDEX IF NOT EXISTS ix_instruccion_auditoria_instr
    ON app.instruccion_auditoria (id_instruccion, modificado_en);
CREATE INDEX IF NOT EXISTS ix_instruccion_auditoria_usuario
    ON app.instruccion_auditoria (id_usuario, modificado_en);
COMMENT ON TABLE app.instruccion_auditoria IS
    'Una fila por campo modificado: qué, valor anterior, valor nuevo, quién y cuándo. La escribe el trigger.';

-- Guardia: transiciones válidas y auditoría automática.
CREATE OR REPLACE FUNCTION app.fn_instruccion_guardia() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.unidades_modelo IS DISTINCT FROM OLD.unidades_modelo
       OR NEW.comentario_modelo IS DISTINCT FROM OLD.comentario_modelo
       OR NEW.id_corrida <> OLD.id_corrida
       OR NEW.sk_articulo <> OLD.sk_articulo
       OR NEW.sk_tienda_origen <> OLD.sk_tienda_origen
       OR NEW.sk_tienda_destino <> OLD.sk_tienda_destino THEN
        RAISE EXCEPTION 'La propuesta original del modelo es inmutable (instruccion %)', OLD.id_instruccion;
    END IF;

    IF NEW.estado <> OLD.estado AND NOT ((OLD.estado, NEW.estado) IN (
            ('PROPUESTA', 'EDITADA'), ('PROPUESTA', 'APROBADA'), ('PROPUESTA', 'DESCARTADA'),
            ('EDITADA',   'APROBADA'), ('EDITADA',  'DESCARTADA'),
            ('APROBADA',  'EJECUTADA'), ('APROBADA', 'DESCARTADA'))) THEN
        RAISE EXCEPTION 'Transición de estado inválida: % -> %', OLD.estado, NEW.estado;
    END IF;

    IF (NEW.unidades, NEW.comentario, NEW.estado) IS DISTINCT FROM (OLD.unidades, OLD.comentario, OLD.estado) THEN
        IF NEW.modificado_por IS NULL THEN
            RAISE EXCEPTION 'modificado_por es obligatorio al editar la instrucción %', OLD.id_instruccion;
        END IF;
        NEW.modificado_en := now();

        IF NEW.unidades IS DISTINCT FROM OLD.unidades THEN
            INSERT INTO app.instruccion_auditoria (id_instruccion, campo, valor_anterior, valor_nuevo, id_usuario)
            VALUES (OLD.id_instruccion, 'unidades', OLD.unidades::text, NEW.unidades::text, NEW.modificado_por);
        END IF;
        IF NEW.comentario IS DISTINCT FROM OLD.comentario THEN
            INSERT INTO app.instruccion_auditoria (id_instruccion, campo, valor_anterior, valor_nuevo, id_usuario)
            VALUES (OLD.id_instruccion, 'comentario', OLD.comentario, NEW.comentario, NEW.modificado_por);
        END IF;
        IF NEW.estado IS DISTINCT FROM OLD.estado THEN
            INSERT INTO app.instruccion_auditoria (id_instruccion, campo, valor_anterior, valor_nuevo, id_usuario)
            VALUES (OLD.id_instruccion, 'estado', OLD.estado, NEW.estado, NEW.modificado_por);
        END IF;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_instruccion_guardia ON app.instruccion;
CREATE TRIGGER trg_instruccion_guardia
    BEFORE UPDATE ON app.instruccion
    FOR EACH ROW EXECUTE FUNCTION app.fn_instruccion_guardia();

-- Las instrucciones y su auditoría no se borran: son evidencia del indicador de confianza.
CREATE OR REPLACE FUNCTION app.fn_bloquear_borrado() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'No se permite borrar % (evidencia de auditoría)', TG_TABLE_NAME;
END $$;

DROP TRIGGER IF EXISTS trg_instruccion_sin_borrado ON app.instruccion;
CREATE TRIGGER trg_instruccion_sin_borrado BEFORE DELETE ON app.instruccion
    FOR EACH ROW EXECUTE FUNCTION app.fn_bloquear_borrado();
DROP TRIGGER IF EXISTS trg_auditoria_inmutable ON app.instruccion_auditoria;
CREATE TRIGGER trg_auditoria_inmutable BEFORE UPDATE OR DELETE ON app.instruccion_auditoria
    FOR EACH ROW EXECUTE FUNCTION app.fn_bloquear_borrado();

-- Indicador de confianza
CREATE OR REPLACE VIEW app.v_instruccion_desviacion AS
SELECT i.id_instruccion,
       i.id_corrida,
       i.sk_articulo,
       i.unidades_modelo,
       i.unidades,
       i.unidades - i.unidades_modelo                          AS delta_unidades,
       ABS(i.unidades - i.unidades_modelo) / i.unidades_modelo AS desviacion_relativa,
       (i.comentario IS DISTINCT FROM i.comentario_modelo)     AS comentario_alterado,
       i.modificado_por,
       i.modificado_en
  FROM app.instruccion i
 WHERE i.unidades <> i.unidades_modelo
    OR i.comentario IS DISTINCT FROM i.comentario_modelo;

-- Instrucciones de la corrida vigente (lo que muestra el módulo)
CREATE OR REPLACE VIEW app.v_instruccion_vigente AS
SELECT i.*
  FROM app.instruccion i
  JOIN app.corrida_modelo c ON c.id_corrida = i.id_corrida AND c.es_vigente;
