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
