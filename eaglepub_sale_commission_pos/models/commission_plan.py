from odoo import fields, models


class EaglepubCommissionPlan(models.Model):
    _inherit = 'eaglepub.commission.plan'

    include_pos = fields.Boolean(
        string='Include POS Sales',
        default=True,
        help='Also commission what this plan\'s salespeople ring up at the till. '
             'Till sales are paid on the spot, so they are counted whichever '
             'basis the plan uses.',
    )
