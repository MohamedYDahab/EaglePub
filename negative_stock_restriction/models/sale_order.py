import logging
from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('negative_stock_restriction.enabled', 'True')
        so_enabled = ICP.get_param('negative_stock_restriction.so_enabled', 'True')

        if enabled == 'True' and so_enabled == 'True':
            mode = ICP.get_param('negative_stock_restriction.mode', 'hard')
            qty_type = ICP.get_param(
                'negative_stock_restriction.qty_type', 'available')
            bypass = self.env.user.has_group(
                'negative_stock_restriction.group_bypass_negative_stock'
            )

            for order in self:
                issues = []
                warehouse = order.warehouse_id

                # Check per-warehouse exception
                if warehouse and warehouse.allow_negative_stock:
                    continue

                for line in order.order_line:
                    product = line.product_id
                    if not product or product.type != 'product':
                        continue

                    # Check per-product exception
                    if product.allow_negative_stock or \
                       product.product_tmpl_id.allow_negative_stock:
                        continue

                    # Check per-category exception
                    if product.categ_id and product.categ_id.allow_negative_stock:
                        continue

                    # Get quantity based on configured type
                    ctx = {'warehouse': warehouse.id} if warehouse else {}
                    p_ctx = product.with_context(**ctx) if ctx else product
                    if qty_type == 'on_hand':
                        avail = p_ctx.qty_available
                    elif qty_type == 'forecast':
                        avail = p_ctx.virtual_available
                    else:
                        # Default: available (on hand - reserved)
                        avail = p_ctx.free_qty

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
                    msg = _("Insufficient Stock for Order %(order)s:\n",
                            order=order.name)
                    msg += "\n".join(issues)
                    msg += "\n\nمخزون غير كافٍ للطلب"

                    if mode == 'hard' and not bypass:
                        raise UserError(msg)
                    else:
                        # Soft mode: log warning and continue
                        _logger.warning(
                            "Neg stock SO warning: %s\n%s",
                            order.name, "\n".join(issues)
                        )
                        # Post a note on the order
                        order.message_post(
                            body=_("⚠️ Low Stock Warning:\n%s") % "\n".join(issues),
                            message_type='notification',
                        )

        return super().action_confirm()
