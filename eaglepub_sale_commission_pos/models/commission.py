from odoo import fields, models


class EaglepubCommissionLine(models.Model):
    _inherit = 'eaglepub.commission.line'

    pos_order_id = fields.Many2one(
        comodel_name='pos.order',
        string='POS Order',
        help='The till order this line came from, when it did not come from an '
             'invoice or a sales order.',
    )
