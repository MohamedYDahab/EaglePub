from odoo import models, fields, api, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    lot_ids = fields.Many2many('stock.lot', compute="get_lot_ids")

    def get_lot_ids(self):
        for rec in self:
            lot_ids = rec.sale_line_ids.lot_ids or rec.purchase_line_id.lot_ids
            rec.lot_ids = lot_ids
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': _('Lots / Serials'),
            'view_mode': 'tree',
            'view_id': self.env.ref('lots_serials_in_invoice_lines.stock_lot_custom_tree').id,
            'res_model': 'stock.lot',
            'domain': [('id', 'in', lot_ids.ids)],
        }
