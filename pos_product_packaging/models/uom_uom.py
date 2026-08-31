# -*- coding: utf-8 -*-

from odoo import models, fields, api


class UomUom(models.Model):
    """Packagings in Odoo 19 are units of measure.

    The old ``product.packaging`` model is gone. What replaced it is a
    ``uom.uom`` record listed in ``product.template.uom_ids`` - Odoo labels that
    field "Packagings". ``product.uom`` is a different thing entirely: a link
    table whose only job is to carry a barcode for one product + unit pair, with
    ``barcode`` required, so it holds nothing at all unless somebody has been
    assigning barcodes.
    """

    _inherit = 'uom.uom'

    available_in_pos = fields.Boolean(
        string='Available in POS',
        default=False,
        help='Offer this unit as a packaging in the POS packaging popup.\n'
             'This is a property of the unit itself, so it applies to every '
             'product that lists this unit under Packagings.',
    )

    @api.model
    def _load_pos_data_fields(self, config):
        data = super()._load_pos_data_fields(config)
        if 'available_in_pos' not in data:
            data.append('available_in_pos')
        return data
