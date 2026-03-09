import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def get_neg_stock_settings(self):
        """Return all negative stock settings for POS frontend."""
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'enabled': ICP.get_param(
                'negative_stock_restriction.enabled', 'True') == 'True',
            'pos_enabled': ICP.get_param(
                'negative_stock_restriction.pos_enabled', 'True') == 'True',
            'mode': ICP.get_param(
                'negative_stock_restriction.mode', 'hard'),
            'threshold': int(ICP.get_param(
                'negative_stock_restriction.threshold', '5')),
            'qty_type': ICP.get_param(
                'negative_stock_restriction.qty_type', 'available'),
            'show_in_pos': ICP.get_param(
                'negative_stock_restriction.show_in_pos', 'True') == 'True',
            'hide_out_of_stock': ICP.get_param(
                'negative_stock_restriction.hide_out_of_stock', 'False') == 'True',
            'refresh_interval': int(ICP.get_param(
                'negative_stock_restriction.refresh_interval', '15')),
            'manager_override': ICP.get_param(
                'negative_stock_restriction.manager_override', 'False') == 'True',
            'bypass': self.env.user.has_group(
                'negative_stock_restriction.group_bypass_negative_stock'),
            'is_manager': self.env.user.has_group(
                'negative_stock_restriction.group_neg_stock_manager'),
        }

    @api.model
    def verify_manager_pin(self, pin):
        """Verify the manager override PIN."""
        ICP = self.env['ir.config_parameter'].sudo()
        stored_pin = ICP.get_param(
            'negative_stock_restriction.manager_pin', '0000')
        is_manager = self.env.user.has_group(
            'negative_stock_restriction.group_neg_stock_manager')
        return {
            'valid': str(pin) == str(stored_pin) and is_manager,
            'is_manager': is_manager,
        }

    @api.model
    def _get_product_qty(self, product, location, qty_type):
        """Get product quantity based on configured type.

        - on_hand: total physical stock (qty_available / quantity on quant)
        - available: on hand minus reserved (_get_available_quantity)
        - forecast: virtual_available (on hand - reserved + incoming - outgoing)
        """
        if qty_type == 'on_hand':
            if location:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', location.id),
                ])
                return sum(quants.mapped('quantity'))
            return product.qty_available
        elif qty_type == 'forecast':
            if location:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', location.id),
                ])
                on_hand = sum(quants.mapped('quantity'))
                reserved = sum(quants.mapped('reserved_quantity'))
                incoming = sum(self.env['stock.move'].search([
                    ('product_id', '=', product.id),
                    ('location_dest_id', '=', location.id),
                    ('state', 'in', ('waiting', 'confirmed', 'assigned')),
                ]).mapped('product_uom_qty'))
                outgoing = sum(self.env['stock.move'].search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', location.id),
                    ('state', 'in', ('waiting', 'confirmed', 'assigned')),
                ]).mapped('product_uom_qty'))
                return on_hand - reserved + incoming - outgoing
            return product.virtual_available
        else:
            # Default: available (on hand - reserved)
            if location:
                return self.env['stock.quant']._get_available_quantity(
                    product, location, strict=False)
            return product.free_qty

    @api.model
    def get_stock_for_products(self, product_ids, location_id=False):
        """Get stock levels for products, respecting all exception rules."""
        _logger.info(
            "[NegStock] get_stock_for_products called with "
            "product_ids=%s, location_id=%s",
            product_ids, location_id,
        )
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param(
            'negative_stock_restriction.enabled', 'True')
        pos_enabled = ICP.get_param(
            'negative_stock_restriction.pos_enabled', 'True')
        mode = ICP.get_param(
            'negative_stock_restriction.mode', 'hard')
        threshold = int(ICP.get_param(
            'negative_stock_restriction.threshold', '5'))
        qty_type = ICP.get_param(
            'negative_stock_restriction.qty_type', 'available')
        show_in_pos = ICP.get_param(
            'negative_stock_restriction.show_in_pos', 'True') == 'True'
        hide_oos = ICP.get_param(
            'negative_stock_restriction.hide_out_of_stock', 'False') == 'True'
        manager_override = ICP.get_param(
            'negative_stock_restriction.manager_override', 'False') == 'True'

        _logger.info(
            "[NegStock] Settings: enabled=%s, pos_enabled=%s, mode=%s, "
            "qty_type=%s",
            enabled, pos_enabled, mode, qty_type,
        )

        if enabled != 'True' or pos_enabled != 'True':
            _logger.info("[NegStock] DISABLED — returning enabled=False")
            return {
                'enabled': False, 'mode': mode, 'stock': {},
                'threshold': threshold, 'show_in_pos': show_in_pos,
                'hide_out_of_stock': hide_oos,
                'manager_override': manager_override,
            }

        # Determine source location
        location = False
        if location_id:
            location = self.env['stock.location'].browse(location_id)
        else:
            sess = self.search([
                ('state', '=', 'opened'),
                ('user_id', '=', self.env.uid),
            ], limit=1)
            _logger.info(
                "[NegStock] Session search: found=%s, config=%s, "
                "picking_type=%s",
                bool(sess),
                sess.config_id.name if sess else 'N/A',
                sess.config_id.picking_type_id.name
                if sess and sess.config_id.picking_type_id else 'N/A',
            )
            if sess and sess.config_id.picking_type_id:
                location = sess.config_id.picking_type_id \
                    .default_location_src_id

        _logger.info(
            "[NegStock] Location resolved: %s (id=%s)",
            location.complete_name if location else 'NONE',
            location.id if location else False,
        )

        # Check warehouse-level exception
        warehouse_exempt = False
        if location and location.warehouse_id:
            warehouse_exempt = location.warehouse_id.allow_negative_stock

        result = {}
        exempt = {}
        products = self.env['product.product'].browse(product_ids)

        for p in products:
            # Check all exception levels
            is_exempt = (
                warehouse_exempt
                or p.allow_negative_stock
                or p.product_tmpl_id.allow_negative_stock
                or (p.categ_id and p.categ_id.allow_negative_stock)
            )
            exempt[p.id] = bool(is_exempt)

            # Odoo 18/19: use is_storable instead of type == 'product'
            if not p.is_storable:
                result[p.id] = 9999999
                _logger.info(
                    "[NegStock]   Product %s (id=%s): NOT storable → 9999999",
                    p.display_name, p.id,
                )
                continue

            qty = self._get_product_qty(p, location, qty_type)
            result[p.id] = qty
            _logger.info(
                "[NegStock]   Product %s (id=%s): storable, "
                "qty=%s, exempt=%s",
                p.display_name, p.id, qty, is_exempt,
            )

        bypass = self.env.user.has_group(
            'negative_stock_restriction.group_bypass_negative_stock')
        is_manager = self.env.user.has_group(
            'negative_stock_restriction.group_neg_stock_manager')

        _logger.info(
            "[NegStock] Result: stock=%s, bypass=%s, mode=%s",
            result, bypass, mode,
        )

        return {
            'enabled': True,
            'mode': mode,
            'stock': result,
            'exempt': exempt,
            'bypass': bypass,
            'is_manager': is_manager,
            'threshold': threshold,
            'qty_type': qty_type,
            'show_in_pos': show_in_pos,
            'hide_out_of_stock': hide_oos,
            'manager_override': manager_override,
        }

    @api.model
    def get_all_product_stock(self, location_id=False):
        """Get stock for ALL storable products — used for POS badge display."""
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param(
            'negative_stock_restriction.enabled', 'True')
        pos_enabled = ICP.get_param(
            'negative_stock_restriction.pos_enabled', 'True')
        show_in_pos = ICP.get_param(
            'negative_stock_restriction.show_in_pos', 'True') == 'True'
        qty_type = ICP.get_param(
            'negative_stock_restriction.qty_type', 'available')

        if enabled != 'True' or pos_enabled != 'True' or not show_in_pos:
            return {}

        # Determine source location
        location = False
        if location_id:
            location = self.env['stock.location'].browse(location_id)
        else:
            sess = self.search([
                ('state', '=', 'opened'),
                ('user_id', '=', self.env.uid),
            ], limit=1)
            if sess and sess.config_id.picking_type_id:
                location = sess.config_id.picking_type_id \
                    .default_location_src_id

        if not location:
            return {}

        # Get all quants at this location
        quants = self.env['stock.quant'].search([
            ('location_id', '=', location.id),
        ])

        result = {}

        if qty_type == 'on_hand':
            for q in quants:
                pid = q.product_id.id
                if pid not in result:
                    result[pid] = 0
                result[pid] += q.quantity

        elif qty_type == 'forecast':
            for q in quants:
                pid = q.product_id.id
                if pid not in result:
                    result[pid] = 0
                result[pid] += q.quantity - q.reserved_quantity

            incoming_moves = self.env['stock.move'].search([
                ('location_dest_id', '=', location.id),
                ('state', 'in', ('waiting', 'confirmed', 'assigned')),
            ])
            for m in incoming_moves:
                pid = m.product_id.id
                if pid not in result:
                    result[pid] = 0
                result[pid] += m.product_uom_qty

            outgoing_moves = self.env['stock.move'].search([
                ('location_id', '=', location.id),
                ('state', 'in', ('waiting', 'confirmed', 'assigned')),
            ])
            for m in outgoing_moves:
                pid = m.product_id.id
                if pid not in result:
                    result[pid] = 0
                result[pid] -= m.product_uom_qty

        else:
            # Default: available (on hand - reserved)
            for q in quants:
                pid = q.product_id.id
                if pid not in result:
                    result[pid] = 0
                result[pid] += q.available_quantity

        return result
