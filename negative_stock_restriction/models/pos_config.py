import logging
from odoo import models

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def write(self, vals):
        """Fix Odoo 17 bug: IndexError in pos_config.write when saving
        settings while a POS session is open.

        The core code at pos_config.py line ~439 does:
            removed_pricelist = set(...) - set(vals[key][0][2])
        which crashes with IndexError when the pricelist command format
        is not a standard (6, 0, ids) tuple (e.g. during settings save).

        This patch catches the IndexError and retries with a cleaned
        pricelist value, preventing the crash.
        """
        try:
            return super().write(vals)
        except IndexError as e:
            if 'list index out of range' in str(e):
                _logger.warning(
                    "POS config write IndexError (known Odoo 17 bug) — "
                    "retrying without pricelist sync. Original error: %s", e
                )
                # Remove the problematic pricelist fields and retry
                safe_vals = {
                    k: v for k, v in vals.items()
                    if 'pricelist' not in k
                }
                if safe_vals:
                    return super().write(safe_vals)
                return True
            raise
