import logging

from odoo import models, _
from odoo.exceptions import UserError

from . import neg_stock_settings as settings

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _neg_stock_issues(self):
        """Shortage descriptions per order, respecting every exception level."""
        if not settings.flag(self.env, 'enabled') or \
           not settings.flag(self.env, 'so_enabled'):
            return {}

        qty_type = settings.param(self.env, 'qty_type', 'available')
        issues_by_order = {}

        for order in self:
            warehouse = order.warehouse_id
            if warehouse.allow_negative_stock:
                continue

            issues = []
            for line in order.order_line:
                product = line.product_id
                if not product or product.type != 'product':
                    continue
                if product.allow_negative_stock or \
                   product.categ_id.allow_negative_stock:
                    continue

                scoped = product.with_context(warehouse=warehouse.id) \
                    if warehouse else product
                if qty_type == 'on_hand':
                    avail = scoped.qty_available
                elif qty_type == 'forecast':
                    avail = scoped.virtual_available
                else:
                    avail = scoped.free_qty

                if avail < line.product_uom_qty:
                    issues.append(_(
                        "%(product)s: Available %(available)s, "
                        "Ordered %(demand)s (Warehouse: %(wh)s)",
                        product=product.display_name,
                        available=avail,
                        demand=line.product_uom_qty,
                        wh=warehouse.name if warehouse else _('Default'),
                    ))

            if issues:
                issues_by_order[order] = issues

        return issues_by_order

    def _neg_stock_message(self, issues_by_order):
        """One readable summary covering every order in the set."""
        blocks = []
        for order, issues in issues_by_order.items():
            blocks.append(
                _("Insufficient Stock for Order %(order)s:", order=order.name)
                + "\n" + "\n".join(issues)
            )
        return "\n\n".join(blocks)

    def _neg_stock_post_warning(self, issues_by_order):
        """Leave the audit trail soft mode has always left behind.

        Posted as superuser with an explicit author: mail_thread refuses to
        post at all when it cannot resolve a sender address, and a salesperson
        whose partner has no email must not be blocked from confirming an
        order. sudo() skips that guard, author_id keeps the note attributed to
        whoever actually clicked through the warning.
        """
        author = self.env.user.partner_id
        for order, issues in issues_by_order.items():
            _logger.warning(
                "Neg stock SO warning: %s\n%s", order.name, "\n".join(issues)
            )
            order.sudo().message_post(
                body=_("⚠️ Low Stock Warning:\n%s") % "\n".join(issues),
                message_type='notification',
                author_id=author.id,
            )

    def action_confirm(self):
        # The wizard re-enters this method with the flag set once the user has
        # accepted the warning, which is also the hook programmatic callers
        # can use to skip the check entirely.
        if not self.env.context.get('skip_neg_stock_check'):
            issues_by_order = self._neg_stock_issues()
            if issues_by_order:
                bypass = self.env.user.has_group(
                    'negative_stock_restriction.group_bypass_negative_stock')
                mode = settings.param(self.env, 'mode', 'hard')

                if mode == 'hard' and not bypass:
                    raise UserError(self._neg_stock_message(issues_by_order))

                # Soft mode: ask instead of confirming behind the user's back.
                wizard = self.env['neg.stock.warning.wizard'].create({
                    'order_ids': [(6, 0, self.ids)],
                    'message': self._neg_stock_message(issues_by_order),
                })
                return {
                    'type': 'ir.actions.act_window',
                    'name': _("Low Stock Warning"),
                    'res_model': 'neg.stock.warning.wizard',
                    'res_id': wizard.id,
                    'view_mode': 'form',
                    'target': 'new',
                }

        return super().action_confirm()
