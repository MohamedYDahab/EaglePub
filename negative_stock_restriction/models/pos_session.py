from odoo import models, api

from . import neg_stock_settings as settings


class PosSession(models.Model):
    _inherit = 'pos.session'

    # -- Setting readers ------------------------------------------------

    @api.model
    def _neg_stock_param(self, key, default=None):
        return settings.param(self.env, key, default)

    @api.model
    def _neg_stock_bool(self, key):
        return settings.flag(self.env, key)

    @api.model
    def _neg_stock_int(self, key, default):
        return settings.number(self.env, key, default)

    # -- Location & quantity resolution ---------------------------------

    @api.model
    def _neg_stock_location(self, location_id=False, config_id=False):
        """Resolve the location POS stock should be read from."""
        if location_id:
            return self.env['stock.location'].browse(location_id).exists()

        config = self.env['pos.config'].browse(config_id).exists() \
            if config_id else self.env['pos.config']

        if not config:
            # user_id is whoever *opened* the session, not necessarily the
            # cashier calling us (pos_hr, shared terminals), so fall back to
            # any session still open for the allowed companies.
            session = self.search([
                ('state', '=', 'opened'),
                ('user_id', '=', self.env.uid),
            ], limit=1) or self.search([
                ('state', '=', 'opened'),
                ('company_id', 'in', self.env.companies.ids),
            ], limit=1)
            config = session.config_id

        return config.picking_type_id.default_location_src_id

    @api.model
    def _neg_stock_qty_map(self, products, location, qty_type):
        """Quantity per product.product id, defaulting to 0 with no quant.

        Products that have never been received own no quant at all - they
        still need a (zero) entry, otherwise they are indistinguishable from
        "not a storable product" downstream.
        """
        if not products:
            return {}

        if not location:
            field = {'on_hand': 'qty_available',
                     'forecast': 'virtual_available'}.get(qty_type, 'free_qty')
            return {p.id: p[field] for p in products}

        result = dict.fromkeys(products.ids, 0.0)

        groups = self.env['stock.quant']._read_group(
            [('product_id', 'in', products.ids),
             ('location_id', 'child_of', location.id)],
            groupby=['product_id'],
            aggregates=['quantity:sum', 'reserved_quantity:sum'],
        )
        for product, on_hand, reserved in groups:
            result[product.id] = (on_hand or 0.0) if qty_type == 'on_hand' \
                else (on_hand or 0.0) - (reserved or 0.0)

        if qty_type == 'forecast':
            base = [('product_id', 'in', products.ids),
                    ('state', 'in', ('waiting', 'confirmed', 'assigned'))]
            for field, sign in (('location_dest_id', 1), ('location_id', -1)):
                moves = self.env['stock.move']._read_group(
                    base + [(field, 'child_of', location.id)],
                    groupby=['product_id'],
                    aggregates=['product_qty:sum'],
                )
                for product, qty in moves:
                    result[product.id] += sign * (qty or 0.0)

        return result

    # -- Frontend entry points ------------------------------------------

    @api.model
    def get_neg_stock_settings(self):
        """Return all negative stock settings for POS frontend."""
        return {
            'enabled': self._neg_stock_bool('enabled'),
            'pos_enabled': self._neg_stock_bool('pos_enabled'),
            'mode': self._neg_stock_param('mode', 'hard'),
            'threshold': self._neg_stock_int('threshold', 5),
            'qty_type': self._neg_stock_param('qty_type', 'available'),
            'show_in_pos': self._neg_stock_bool('show_in_pos'),
            'hide_out_of_stock': self._neg_stock_bool('hide_out_of_stock'),
            'refresh_interval': self._neg_stock_int('refresh_interval', 15),
            'manager_override': self._neg_stock_bool('manager_override'),
            'bypass': self.env.user.has_group(
                'negative_stock_restriction.group_bypass_negative_stock'),
            'is_manager': self.env.user.has_group(
                'negative_stock_restriction.group_neg_stock_manager'),
        }

    @api.model
    def verify_manager_pin(self, pin):
        """Verify the manager override PIN."""
        stored_pin = self._neg_stock_param('manager_pin', '0000')
        is_manager = self.env.user.has_group(
            'negative_stock_restriction.group_neg_stock_manager')
        return {
            'valid': str(pin) == str(stored_pin) and is_manager,
            'is_manager': is_manager,
        }

    @api.model
    def get_stock_for_products(self, product_ids, location_id=False,
                               config_id=False):
        """Stock levels per product.product id, respecting every exception.

        Keyed by variant because that is what an orderline carries:
        ``orderline.getProduct()`` returns ``product_id``.
        """
        base = {
            'mode': self._neg_stock_param('mode', 'hard'),
            'threshold': self._neg_stock_int('threshold', 5),
            'qty_type': self._neg_stock_param('qty_type', 'available'),
            'show_in_pos': self._neg_stock_bool('show_in_pos'),
            'hide_out_of_stock': self._neg_stock_bool('hide_out_of_stock'),
            'manager_override': self._neg_stock_bool('manager_override'),
        }

        if not self._neg_stock_bool('enabled') or \
           not self._neg_stock_bool('pos_enabled'):
            return dict(base, enabled=False, stock={}, exempt={})

        location = self._neg_stock_location(location_id, config_id)
        products = self.env['product.product'].browse(product_ids).exists()
        storable = products.filtered('is_storable')
        qty_map = self._neg_stock_qty_map(storable, location, base['qty_type'])

        warehouse_exempt = bool(
            location.warehouse_id and location.warehouse_id.allow_negative_stock
        ) if location else False

        stock, exempt = {}, {}
        for product in products:
            exempt[product.id] = bool(
                warehouse_exempt
                or product.allow_negative_stock
                or product.categ_id.allow_negative_stock
            )
            # Anything not storable is never short of stock.
            stock[product.id] = qty_map.get(product.id, 9999999)

        return dict(
            base,
            enabled=True,
            stock=stock,
            exempt=exempt,
            bypass=self.env.user.has_group(
                'negative_stock_restriction.group_bypass_negative_stock'),
            is_manager=self.env.user.has_group(
                'negative_stock_restriction.group_neg_stock_manager'),
        )

    @api.model
    def get_all_product_stock(self, location_id=False, config_id=False,
                              product_tmpl_ids=None):
        """Stock per product.template id, for the POS badges.

        Keyed by *template*, not variant: since Odoo 18 the product screen
        renders product.template records and stamps data-product-id with the
        template id, while stock lives on the variants. A template's badge
        therefore shows the sum over its storable variants.
        """
        if not self._neg_stock_bool('enabled') or \
           not self._neg_stock_bool('pos_enabled') or \
           not self._neg_stock_bool('show_in_pos'):
            return {}

        Template = self.env['product.template']
        templates = Template.browse(product_tmpl_ids).exists() \
            if product_tmpl_ids \
            else Template.search([('available_in_pos', '=', True)])
        templates = templates.filtered('is_storable')
        if not templates:
            return {}

        qty_map = self._neg_stock_qty_map(
            templates.product_variant_ids,
            self._neg_stock_location(location_id, config_id),
            self._neg_stock_param('qty_type', 'available'),
        )

        return {
            template.id: sum(
                qty_map.get(variant.id, 0.0)
                for variant in template.product_variant_ids
            )
            for template in templates
        }
