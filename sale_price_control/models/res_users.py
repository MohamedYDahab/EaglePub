from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    price_override_password = fields.Char(
        string='Price Override Password',
        copy=False,
        help='Password required to authorize setting a sale price below product cost price.',
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['price_override_password']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['price_override_password']
