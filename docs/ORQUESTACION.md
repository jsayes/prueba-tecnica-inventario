# Estrategia de orquestación

> Plantilla a completar por el candidato. Esta prueba exige la estrategia **implementada y ejecutable**, no solo documentada.

## 1. Herramienta seleccionada

**Elección:**

**Justificación:**

| Herramienta | Ventajas | Desventajas | Por qué (no) la elegí |
|---|---|---|---|
| | | | |

## 2. Diseño de los flujos

| Flujo | Frecuencia | Ventana | Depende de | Reintentos | Timeout | Acción ante fallo |
|---|---|---|---|---|---|---|
| Catálogos (dimensiones) | | | | | | |
| Ventas intradía (3 cortes) | | | | | | |
| Inventario intradía (30 min) | | | | | | |
| Cierre diario de inventario | | | | | | |
| Refresco de objetos de KPIs | | | | | | |
| Cargas históricas | Una vez | — | — | | | |

### 2.1 Diagrama

```mermaid
flowchart LR
    %% Reemplazar con tu diseño
```

## 3. Preguntas que la estrategia debe responder

- **Concurrencia:** el snapshot de las 08:00 empieza mientras el de las 07:30 aún corre. ¿Qué pasa?
- **Solapamiento de cortes:** los cortes de ventas son acumulados. ¿Cómo evitas duplicar o perder ventas?
- **Fallo aislado:** el snapshot de las 07:30 falla. ¿Se detiene la cadena, se salta, se reintenta? ¿El cierre diario puede correr con un snapshot faltante?
- **Ventas tardías:** llegan ventas con fecha del día anterior. ¿Reprocesas el día anterior? ¿Automáticamente o a mano?
- **Backfill:** cómo reprocesar un día o un rango, y por qué es seguro hacerlo.
- **Alertamiento:** qué se notifica, a quién y con qué umbral (por ejemplo, ratio de rechazo sobre el máximo configurado).
- **Dependencia con las dimensiones:** un artículo nuevo aparece en una venta antes de estar en el catálogo. ¿Qué hace el flujo?

## 4. Cómo ejecutarlo

Comandos exactos para levantar el orquestador, registrar los flujos y disparar un backfill.

```bash
# comandos
```
