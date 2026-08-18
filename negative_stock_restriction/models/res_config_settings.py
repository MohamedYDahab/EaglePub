from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Core Settings ──────────────────────────────────────────────────
    neg_stock_enabled = fields.Boolean(
        string="Enable Negative Stock Restriction",
        config_parameter='negative_stock_restriction.enabled',
    )
    neg_stock_mode = fields.Selection(
        [('hard', 'Hard Block'), ('soft', 'Soft Warning')],
        string="Restriction Mode",
        config_parameter='negative_stock_restriction.mode',
        default='hard',
    )

    # ── Module-specific toggles ────────────────────────────────────────
    neg_stock_stock_enabled = fields.Boolean(
        string="Enable in Stock Transfers",
        config_parameter='negative_stock_restriction.stock_enabled',
    )
    neg_stock_pos_enabled = fields.Boolean(
        string="Enable in Point of Sale",
        config_parameter='negative_stock_restriction.pos_enabled',
    )
    neg_stock_so_enabled = fields.Boolean(
        string="Enable in Sale Orders",
        help="Check stock when confirming Sale Orders",
        config_parameter='negative_stock_restriction.so_enabled',
    )

    # ── Threshold / Buffer ─────────────────────────────────────────────
    neg_stock_threshold = fields.Integer(
        string="Low Stock Warning Threshold",
        help="Show a yellow/warning badge in POS when stock is at or below this value. "
             "Set to 0 to only warn when fully out of stock.",
        config_parameter='negative_stock_restriction.threshold',
        default=5,
    )

    # ── Quantity Type ──────────────────────────────────────────────────
    neg_stock_qty_type = fields.Selection(
        [('on_hand', 'On Hand (Total Physical)'),
         ('available', 'Forecast Quantity'),
         ('forecast', '(On Hand − Reserved + Incoming − Outgoing)')],
        string="Stock Quantity Type",
        help="Which quantity to check and display:\n"
             "• On Hand: total physical stock in the location\n"
             "• Available: on hand minus reserved quantities\n"
             "• Forecast: available plus incoming minus outgoing",
        config_parameter='negative_stock_restriction.qty_type',
        default='available',
    )

    # ── POS Display Settings ───────────────────────────────────────────
    neg_stock_show_in_pos = fields.Boolean(
        string="Show Stock on POS Product Cards",
        help="Display real-time stock quantity badges on product cards in POS",
        config_parameter='negative_stock_restriction.show_in_pos',
    )
    neg_stock_hide_out_of_stock = fields.Boolean(
        string="Auto-Hide Out-of-Stock Products",
        help="Automatically hide products with zero or negative stock from POS product list",
        config_parameter='negative_stock_restriction.hide_out_of_stock',
        default=False,
    )
    neg_stock_refresh_interval = fields.Integer(
        string="POS Stock Refresh Interval (seconds)",
        help="How often to auto-refresh stock quantities on POS product cards. "
             "Stock also refreshes instantly after every completed order. "
             "Set to 0 to disable auto-refresh (only refresh after orders).",
        config_parameter='negative_stock_restriction.refresh_interval',
        default=15,
    )

    # ── Manager Override ───────────────────────────────────────────────
    neg_stock_manager_override = fields.Boolean(
        string="Allow Manager Override",
        help="Allow managers to override hard blocks using a PIN/password",
        config_parameter='negative_stock_restriction.manager_override',
        default=False,
    )
    neg_stock_manager_pin = fields.Char(
        string="Manager Override PIN",
        help="PIN code required to override negative stock blocks in POS",
        config_parameter='negative_stock_restriction.manager_pin',
        default='0000',
    )

    def set_values(self):
        """Persist this module's zero-valued integers.

        ``res.config.settings`` maps ``0`` to ``False`` and ``set_param`` then
        *deletes* the record, so a threshold or interval of 0 would silently
        fall back to its default. Booleans are left alone: Odoo represents an
        unticked box as an absent parameter, and ``default_get`` reads any
        stored string back as ``bool(value)`` -- so writing the literal
        ``'False'`` would render the box as ticked.
        """
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        for name, icp in self._get_classified_fields()['config']:
            # Other modules read their own parameters their own way; only
            # touch the ones this module owns.
            if not icp.startswith('negative_stock_restriction.'):
                continue
            if self._fields[name].type == 'integer' and not self[name]:
                ICP.set_param(icp, '0')
