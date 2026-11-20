# Modelo de datos — secciones 6 y 7

> Plantilla a completar por el candidato. Las secciones 1 a 4 (dimensional, raw y control de ETL) y la 5 (autenticación y autorización) vienen entregadas. Aquí documentas lo que agregaste.

## 1. Instrucciones y su auditoría (sección 6)

### 1.1 Tablas que agregué

| Tabla | Grano | Llaves | Justificación |
|---|---|---|---|
| | | | |

### 1.2 Decisiones

- **¿Auditoría por campo o por versión completa de la instrucción?** ¿Qué gana y qué pierde tu opción?
- **¿Cómo conservas la propuesta original del modelo** cuando un humano edita la instrucción?
- **¿Las instrucciones referencian la llave surrogada o la natural** de artículo y tienda? ¿Qué pasa cuando la dimensión versiona?
- **¿Cómo garantizas una sola corrida vigente a la vez?**
- **¿Qué restricciones pusiste a nivel de base de datos** (estados válidos, origen distinto de destino, unidades positivas) y qué dejaste a la aplicación?

### 1.3 Consulta de comprobación

```sql
-- ¿Cuáles instrucciones fueron alteradas por un humano el mes pasado
-- y en qué magnitud respecto a lo que propuso el modelo?
```

## 2. Capa de consumo de KPIs (sección 7)

### 2.1 Arquitectura propuesta

Qué estructura elegiste para la capa `analytics`, con qué granos, y **por qué es la adecuada para el patrón de consumo del dashboard**. Este es el punto que más pesa del apartado: se evalúa el argumento, no la cantidad de objetos.

| Objeto | Tipo | Grano | KPIs que resuelve | Cómo se actualiza |
|---|---|---|---|---|
| | | | | |

### 2.2 Alternativas que descarté

| Alternativa | Por qué no |
|---|---|
| | |

### 2.3 Costos de mi propuesta

Qué se vuelve más difícil o más caro con la estructura que elegiste: almacenamiento, latencia del dato, complejidad del ETL, mantenimiento.

## 3. Cambios al modelo entregado

Si modificaste algo de las secciones 1 a 5, documéntalo aquí.

| # | Cambio | Motivo |
|---|---|---|

## 4. DER de lo que agregué

```mermaid
erDiagram
    %% secciones 6 y 7
```
