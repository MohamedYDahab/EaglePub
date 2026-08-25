import logging
import re

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    eaglepub_ocr_purchase_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Matched Purchase Order',
        copy=False,
        readonly=True,
        help='The order this digitised bill was matched to, when its reference '
             'appeared on the supplier document.',
    )

    def _eaglepub_prepare_values(self, values):
        """Link the order named on the document, if there is one."""
        vals = super()._eaglepub_prepare_values(values)
        order = self._eaglepub_find_purchase_order(values)
        if order:
            vals['eaglepub_ocr_purchase_id'] = order.id
            vals['invoice_origin'] = order.name
            # Only adopt the vendor from the order when the document did not
            # yield one. The printed document is the better evidence of who is
            # actually billing you.
            if not vals.get('partner_id'):
                vals['partner_id'] = order.partner_id.id
        return vals

    def _eaglepub_find_purchase_order(self, values):
        """The order whose name appears on the document.

        Suppliers quote references untidily - "Ref PO00012", "our order
        po-00012" - so the digits are matched rather than the whole string,
        and only against orders that are actually open for billing.
        """
        reference = values.get('purchase_order')
        if not reference:
            return self.env['purchase.order']

        Order = self.env['purchase.order']
        text = reference.strip()

        order = Order.search([
            ('name', '=ilike', text),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if order:
            return order

        digits = re.sub(r'\D', '', text)
        if len(digits) < 3:
            # Too short to identify anything: matching on one or two digits
            # would link the wrong order more often than the right one.
            return Order
        return Order.search([
            ('name', 'ilike', digits),
            ('state', 'in', ('purchase', 'done')),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    def _eaglepub_apply(self, attachment):
        """After the bill is filled, compare it with the order it came from."""
        super()._eaglepub_apply(attachment)
        self._eaglepub_check_against_purchase()

    def _eaglepub_check_against_purchase(self):
        """Flag a bill that does not agree with its purchase order.

        Deliberately additive: if the arithmetic check already flagged this
        bill, that message is kept and this one appended, because both problems
        are worth knowing about at once.
        """
        self.ensure_one()
        order = self.eaglepub_ocr_purchase_id
        if not order:
            return

        billed = self.amount_untaxed
        ordered = order.amount_untaxed
        gap = billed - ordered
        if abs(gap) <= max(0.02, abs(ordered) * 0.005):
            self.message_post(body=_(
                'Matched to %(order)s, and the amounts agree.', order=order.name))
            return

        note = _(
            'Billed %(billed).2f against %(order)s at %(ordered).2f - a difference '
            'of %(gap).2f.',
            billed=billed, order=order.name, ordered=ordered, gap=gap,
        )
        existing = self.eaglepub_ocr_message
        self.sudo().write({
            'eaglepub_ocr_state': 'check',
            'eaglepub_ocr_message': ('%s %s' % (existing, note)).strip() if existing else note,
        })
        self.message_post(body=note)
