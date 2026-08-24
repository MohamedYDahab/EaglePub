from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    purchase_target_alert_tolerance = fields.Float(
        related='company_id.purchase_target_alert_tolerance',
        readonly=False,
    )
