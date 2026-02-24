from odoo import fields, models
from odoo.exceptions import UserError


class PriceOverrideWizard(models.TransientModel):
    _name = 'price.override.wizard'
    _description = 'Price Override Authorization Wizard'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        readonly=True,
    )
    line_info = fields.Text(
        string='Below Cost Lines',
        readonly=True,
    )
    password = fields.Char(
        string='Authorization Password',
    )

    def action_authorize_and_confirm(self):
        """Verify password, mark below-cost lines as approved, confirm order."""
        self.ensure_one()
        user = self.env.user

        # 1. Validate password was entered
        if not self.password:
            raise UserError('Please enter a password.')

        # 2. Check group membership
        if not user.has_group('sale_price_control.group_price_override'):
            raise UserError(
                'You do not belong to the "Allow Below Cost Price" group.\n'
                'Contact your administrator.'
            )

        # 3. Check password is configured on user
        if not user.price_override_password:
            raise UserError(
                'No price override password is configured for your user.\n'
                'Please set one in Settings → Users → Preferences.'
            )

        # 4. Verify password matches
        if user.price_override_password != self.password:
            raise UserError('Incorrect password.')

        # 5. Mark all below-cost lines as approved
        order = self.sale_order_id
        below_cost_lines = order._get_below_cost_lines()
        below_cost_lines.write({'price_override_approved': True})

        # 6. Now confirm the order (will pass since lines are approved)
        return order.action_confirm()
