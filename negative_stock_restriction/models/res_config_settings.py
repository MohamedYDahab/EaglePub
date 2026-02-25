from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    neg_stock_enabled = fields.Boolean(
        string="Enable Negative Stock Restriction",
        config_parameter='negative_stock_restriction.enabled', default=True)
    neg_stock_mode = fields.Selection(
        [('hard', 'Hard Block'), ('soft', 'Soft Warning')],
        string="Restriction Mode",
        config_parameter='negative_stock_restriction.mode', default='hard')
    neg_stock_pos_enabled = fields.Boolean(
        string="Enable in POS",
        config_parameter='negative_stock_restriction.pos_enabled', default=True)
    neg_stock_stock_enabled = fields.Boolean(
        string="Enable in Stock Transfers",
        config_parameter='negative_stock_restriction.stock_enabled', default=True)
