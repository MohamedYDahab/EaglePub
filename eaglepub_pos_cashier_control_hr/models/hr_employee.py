from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    eaglepub_pos_policy_id = fields.Many2one(
        comodel_name='eaglepub.pos.policy',
        string='POS Policy',
        help='Limits applied to this employee at the till. Leave empty to fall '
             'back to the policy on their Odoo user, if they have one.',
    )

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['eaglepub_pos_policy_id']
