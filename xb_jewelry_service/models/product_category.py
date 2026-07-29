from odoo import fields, models


class ProductCategory(models.Model):
    """El tipo de pieza sale del árbol de categorías que la tienda ya tiene.

    Inventar una lista propia obligaría a mantener dos vocabularios. Lo único
    que hace falta es decirle al módulo qué categorías son joyería y de qué
    naturaleza, para que la lista de fotos sepa si pedir medida o largo.
    """

    _inherit = "product.category"

    xb_jewelry_kind = fields.Selection(
        [
            ("ring", "Ring"),
            ("chain", "Chain or bracelet"),
            ("other", "Other piece"),
        ],
        string="Jewelry kind",
        help="Mark the categories that describe a customer piece. Only these "
        "are offered when a piece is received, and the kind decides which "
        "measurements and photos are asked for.",
    )
