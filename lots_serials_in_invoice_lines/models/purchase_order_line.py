# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        string='Lots / Serials',
        compute='_compute_lot_ids',
        help='Lot/Serial numbers from related stock moves',
    )

    @api.depends('move_ids', 'move_ids.lot_ids')
    def _compute_lot_ids(self):
        for line in self:
            line.lot_ids = line.move_ids.lot_ids

    def action_view_lots(self):
        """Button action: open lots in a popup tree view."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': _('Lots / Serials'),
            'view_mode': 'tree',
            'view_id': self.env.ref(
                'lots_serials_in_invoice_lines.stock_lot_custom_tree'
            ).id,
            'res_model': 'stock.lot',
            'domain': [('id', 'in', self.lot_ids.ids)],
        }
