from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    eaglepub_pos_policy_id = fields.Many2one(
        comodel_name='eaglepub.pos.policy',
        string='POS Policy',
        help='Limits applied to this cashier at the till. '
             'Leave empty for no restrictions.',
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['eaglepub_pos_policy_id']

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['eaglepub_pos_policy_id']
