# -*- coding: utf-8 -*-

from odoo import models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if 'qty_available' not in fields_list:
            fields_list.append('qty_available')
        if 'uom_ids' not in fields_list:
            fields_list.append('uom_ids')
        return fields_list
