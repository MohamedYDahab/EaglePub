# -*- coding: utf-8 -*-

from odoo import models, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_product_packaging(self):
        result = super()._loader_params_product_packaging()
        # Add available_in_pos to fields
        if 'fields' in result.get('search_params', {}):
            if 'available_in_pos' not in result['search_params']['fields']:
                result['search_params']['fields'].append('available_in_pos')
        # Remove barcode requirement - load ALL packagings
        if 'domain' in result.get('search_params', {}):
            # Remove any barcode != False domain
            result['search_params']['domain'] = [
                ('available_in_pos', '!=', False)
            ]
        else:
            result['search_params']['domain'] = [
                ('available_in_pos', '!=', False)
            ]
        return result