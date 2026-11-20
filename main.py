"""CLI del ETL.

Comandos previstos (los de dimensiones ya funcionan):

    python main.py dim-articulo        --fecha-archivo 20260302
    python main.py dim-tienda          --fecha-archivo 20260302
    python main.py ventas-historico    --anio 2024
    python main.py ventas-intradia     --fecha 2026-03-02 --corte 0800
    python main.py inventario-historico --periodo 202512
    python main.py inventario-intradia --fecha 2026-03-02 --hora 0630
    python main.py cerrar-inventario   --fecha 2026-03-02

Puedes cambiar la interfaz si lo justificas, pero debe permitir ejecutar
cualquier flujo para un parámetro dado (esto es lo que habilita el backfill
desde el orquestador).
"""
from __future__ import annotations

import argparse

from src.pipelines import dimensiones, inventario, ventas


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ETL inventario óptimo")
    sub = p.add_subparsers(dest="comando", required=True)

    a = sub.add_parser("dim-articulo")
    a.add_argument("--fecha-archivo", required=True)
    a.set_defaults(fn=lambda x: dimensiones.dim_articulo(x.fecha_archivo).run())

    t = sub.add_parser("dim-tienda")
    t.add_argument("--fecha-archivo", required=True)
    t.set_defaults(fn=lambda x: dimensiones.dim_tienda(x.fecha_archivo).run())

    vh = sub.add_parser("ventas-historico")
    vh.add_argument("--anio", required=True, type=int)
    vh.set_defaults(fn=lambda x: ventas.ventas_historico(x.anio).run())

    vi = sub.add_parser("ventas-intradia")
    vi.add_argument("--fecha", required=True)
    vi.add_argument("--corte", required=True, choices=["0800", "1400", "2000"])
    vi.set_defaults(fn=lambda x: ventas.ventas_intradia(x.fecha, x.corte).run())

    ih = sub.add_parser("inventario-historico")
    ih.add_argument("--periodo", required=True, help="AAAAMM")
    ih.set_defaults(fn=lambda x: inventario.inventario_historico(x.periodo).run())

    ii = sub.add_parser("inventario-intradia")
    ii.add_argument("--fecha", required=True)
    ii.add_argument("--hora", required=True, help="HHMM")
    ii.set_defaults(fn=lambda x: inventario.inventario_intradia(x.fecha, x.hora).run())

    ci = sub.add_parser("cerrar-inventario")
    ci.add_argument("--fecha", required=True)
    ci.set_defaults(fn=lambda x: inventario.cerrar_inventario_dia(x.fecha))

    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.fn(args)
