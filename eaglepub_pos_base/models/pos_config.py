from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    eaglepub_manager_pin = fields.Char(
        string='Manager PIN',
        copy=False,
        help='PIN a manager types at the till to authorise a restricted action. '
             'It is checked on the server and never loaded into the browser.',
    )

    @api.model
    def verify_eaglepub_pin(self, config_id, pin):
        """Check a PIN typed at the till. Returns True only on an exact match.

        Deliberately an RPC rather than a field loaded into the POS payload:
        anything the till loads is readable by whoever is standing at it, which
        would defeat the point of having a manager PIN at all.
        """
        if not pin:
            return False
        config = self.sudo().browse(config_id)
        if not config.exists() or not config.eaglepub_manager_pin:
            return False
        return str(pin).strip() == config.eaglepub_manager_pin.strip()
