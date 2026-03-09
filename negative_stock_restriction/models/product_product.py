from odoo import api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _load_pos_data_fields(self, config):
        """Inject allow_negative_stock into POS product data."""
        fields = super()._load_pos_data_fields(config)
        if 'allow_negative_stock' not in fields:
            fields.append('allow_negative_stock')
        return fields
