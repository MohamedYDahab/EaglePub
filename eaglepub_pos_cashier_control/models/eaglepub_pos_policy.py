from odoo import api, fields, models


class EaglepubPosPolicy(models.Model):
    _name = 'eaglepub.pos.policy'
    _inherit = ['pos.load.mixin']
    _description = 'POS Cashier Policy'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    max_discount = fields.Float(
        string='Maximum Discount (%)',
        default=100.0,
        help='Highest discount a cashier on this policy may put on a line. '
             'Set to 0 to forbid discounts entirely.',
    )
    allow_line_delete = fields.Boolean(
        string='Allow Line Deletion',
        default=True,
        help='When off, a cashier can add lines but not remove them.',
    )
    allow_price_change = fields.Boolean(
        string='Allow Price Change',
        default=True,
        help='When off, the pricelist decides the unit price, not the cashier.',
    )
    max_order_amount = fields.Float(
        string='Maximum Order Total',
        default=0.0,
        help='Orders above this total need manager approval. 0 means no ceiling.',
    )

    user_ids = fields.One2many(
        comodel_name='res.users',
        inverse_name='eaglepub_pos_policy_id',
        string='Cashiers',
    )
    user_count = fields.Integer(compute='_compute_user_count', string='# Cashiers')

    _max_discount_range = models.Constraint(
        'CHECK(max_discount >= 0 AND max_discount <= 100)',
        'Maximum discount must be between 0 and 100 percent.',
    )
    _max_order_amount_positive = models.Constraint(
        'CHECK(max_order_amount >= 0)',
        'Maximum order total cannot be negative.',
    )

    @api.depends('user_ids')
    def _compute_user_count(self):
        for policy in self:
            policy.user_count = len(policy.user_ids)

    # ── POS loading ──
    @api.model
    def _load_pos_data_domain(self, data, config):
        return [('active', '=', True)]

    @api.model
    def _load_pos_data_fields(self, config):
        return [
            'id', 'name', 'max_discount', 'allow_line_delete',
            'allow_price_change', 'max_order_amount',
        ]
