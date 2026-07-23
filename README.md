# XUBAX — Odoo Apps (18.0)

Módulos para **Odoo 18.0** publicados por **XUBAX** ([xubax.com](https://xubax.com) · soporte@xubax.com).

La rama `18.0` contiene el código para Odoo 18.0. Cada módulo vive en su propia carpeta en la raíz del repositorio.

## Módulos

| Módulo | Versión | Precio | Descripción |
|---|---|---|---|
| `xb_product_pricelist_rules` | 18.0.1.0.0 | Gratis (LGPL-3) | Muestra **todas** las reglas de lista de precio (incl. fórmula y porcentaje) en el smart button del producto, y agrega un menú buscable de reglas. Corrige el límite de Odoo 18 que solo contaba reglas de precio fijo. |
| `xb_pos_taecel` | 1.0.0 | 249 USD (OPL-1) | Venta de tiempo aire, paquetes de datos, pago de servicios y pines electrónicos desde el Punto de Venta, contra la red **TAECEL** (México): 30+ operadoras, saldo en vivo y conciliación automática de ventas interrumpidas. |

> **Nota sobre la versión de `xb_pos_taecel`.** Lleva versión de 3 partes (`1.0.0`) a propósito: Odoo le antepone la serie que esté corriendo, así que instala tanto en **18.0** como en las builds **saas~18.x**. Una versión `18.0.1.0.0` queda `installable=False` en un saas~18.3, porque ahí `release.major_version` es literalmente `saas~18.3`. El código es idéntico al de la rama `19.0`: la compatibilidad se resuelve en runtime (ver `static/src/app/compat.js` y `models/pos_compat.py`).

## Soporte

soporte@xubax.com · https://www.xubax.com
