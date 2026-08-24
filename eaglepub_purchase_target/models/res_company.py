from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    purchase_target_alert_tolerance = fields.Float(
        string='Replenishment Alert Tolerance (%)',
        default=5.0,
        help='Shortfall below which a purchase target line is not reported, as '
             'a share of its monthly forecast. Set to zero to alert on any '
             'shortfall at all.',
    )
