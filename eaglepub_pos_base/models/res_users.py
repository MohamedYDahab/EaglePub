from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    eaglepub_pos_manager = fields.Boolean(
        string='POS Manager Override',
        compute='_compute_eaglepub_pos_manager',
        help='True when this user may authorise restricted till actions without typing the PIN.',
    )

    @api.depends('all_group_ids')
    def _compute_eaglepub_pos_manager(self):
        # Resolved through all_group_ids rather than has_group(), which answers
        # for the *current* user rather than the record being computed.
        group = self.env.ref(
            'eaglepub_pos_base.group_eaglepub_pos_manager', raise_if_not_found=False,
        )
        for user in self:
            user.eaglepub_pos_manager = bool(group) and group in user.all_group_ids

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['eaglepub_pos_manager']
