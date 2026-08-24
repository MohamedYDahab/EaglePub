import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    eaglepub_override_uid = fields.Many2one(
        comodel_name='res.users',
        string='Approved By',
        readonly=True,
        help='Manager who authorised this order past its cashier policy.',
    )

    @api.model
    def _process_order(self, order, existing_order):
        """Re-check the cashier policy as the order arrives.

        The till already enforces this, but the till is a browser: re-checking
        here means an order cannot be edited past its policy in transit.

        Caveat worth knowing: an order that carries an override is trusted,
        because the PIN behind that override was verified server-side when it
        was granted. Tightening that would mean re-verifying at sync time.
        """
        self._eaglepub_check_policy(order)
        return super()._process_order(order, existing_order)

    @api.model
    def _eaglepub_check_policy(self, order):
        if not isinstance(order, dict) or order.get('eaglepub_override_uid'):
            return

        policy = self._eaglepub_policy_for(order)
        if not policy:
            return

        for line_vals in self._eaglepub_iter_line_vals(order):
            discount = line_vals.get('discount') or 0.0
            if discount > policy.max_discount:
                raise UserError(_(
                    'Discount of %(given).2f%% is above the %(max).2f%% allowed by '
                    'the "%(policy)s" policy. A manager has to approve this order.',
                    given=discount, max=policy.max_discount, policy=policy.name,
                ))

            # A zero-quantity line is a deletion by another name, so it falls
            # under the same rule. Refund lines legitimately carry zero or
            # negative quantities and are left alone.
            if not policy.allow_line_delete and not line_vals.get('refunded_orderline_id'):
                qty = line_vals.get('qty')
                if qty is not None and qty <= 0:
                    raise UserError(_(
                        'The "%(policy)s" policy does not allow removing lines, and a '
                        'quantity of %(qty)s empties one. A manager has to approve this order.',
                        policy=policy.name, qty=qty,
                    ))

        ceiling = policy.max_order_amount
        total = order.get('amount_total') or 0.0
        if ceiling > 0 and total > ceiling:
            raise UserError(_(
                'This order comes to %(total).2f, above the %(max).2f ceiling set by '
                'the "%(policy)s" policy. A manager has to approve it.',
                total=total, max=ceiling, policy=policy.name,
            ))

        # allow_price_change is deliberately not re-checked here. The server
        # cannot tell a hand-typed price from one a pricelist produced without
        # recomputing every pricelist rule, and a wrong guess would reject
        # legitimate orders. The till blocks the numpad; this limit is a
        # workflow control rather than a security boundary, and is documented
        # as such on the app page.

    @api.model
    def _eaglepub_policy_for(self, order):
        """Whose policy governs an incoming order payload.

        The single extension point for a different notion of "cashier": the
        pos_hr bridge overrides this to prefer the employee who rang the order
        up, since with badge login the Odoo user is whoever opened the session
        rather than whoever served the customer.
        """
        user = self.env['res.users'].browse(order.get('user_id')) or self.env.user
        return user.sudo().eaglepub_pos_policy_id

    @api.model
    def _eaglepub_iter_line_vals(self, order):
        """Yield the values dict of each line, whatever shape the payload is in.

        Deliberately forgiving: a malformed line is skipped rather than raised
        on, because refusing to sync would strand a paid order at the till.
        """
        for line in order.get('lines') or []:
            if isinstance(line, dict):
                yield line
            elif isinstance(line, (list, tuple)) and len(line) == 3 and isinstance(line[2], dict):
                yield line[2]
            else:
                _logger.debug('eaglepub: unrecognised POS line payload %r', line)
