from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_eaglepub_manager_pin = fields.Char(
        related='pos_config_id.eaglepub_manager_pin',
        readonly=False,
    )
