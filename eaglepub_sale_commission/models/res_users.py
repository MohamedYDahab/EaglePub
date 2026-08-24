from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    eaglepub_commission_plan_id = fields.Many2one(
        comodel_name='eaglepub.commission.plan',
        string='Commission Plan',
        help='Leave empty if this person does not earn commission.',
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['eaglepub_commission_plan_id']
