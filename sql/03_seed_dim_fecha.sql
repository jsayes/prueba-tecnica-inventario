-- Poblado de la dimensión de calendario (2022-01-01 a 2027-12-31)
INSERT INTO core.dim_fecha (
    sk_fecha, fecha, anio, trimestre, mes, nombre_mes, dia,
    dia_semana, nombre_dia, semana_iso, es_fin_semana,
    primer_dia_mes, ultimo_dia_mes
)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER,
    d::DATE,
    EXTRACT(YEAR FROM d),
    EXTRACT(QUARTER FROM d),
    EXTRACT(MONTH FROM d),
    TRIM(TO_CHAR(d, 'TMMonth')),
    EXTRACT(DAY FROM d),
    EXTRACT(ISODOW FROM d),
    TRIM(TO_CHAR(d, 'TMDay')),
    EXTRACT(WEEK FROM d),
    EXTRACT(ISODOW FROM d) IN (6, 7),
    DATE_TRUNC('month', d)::DATE,
    (DATE_TRUNC('month', d) + INTERVAL '1 month - 1 day')::DATE
FROM generate_series('2022-01-01'::DATE, '2027-12-31'::DATE, '1 day') AS d
ON CONFLICT (sk_fecha) DO NOTHING;
