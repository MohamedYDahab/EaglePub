# -*- coding: utf-8 -*-
"""Carry the POS flag from product.uom over to the units themselves.

Up to 19.0.1.0.0 ``available_in_pos`` lived on ``product.uom``, so it was set
per product + unit pair. It now lives on ``uom.uom``, which makes it a property
of the unit: enable "Case of 6" once and it is offered wherever a product lists
that unit under Packagings.

This runs after the update because it writes to a column the update creates.
The stored ``packaging_id`` references are handled earlier, in pre-migration,
where they have to be - see that file for why.

The old ``product_uom.available_in_pos`` column is left in place. It is unused
and harmless, and a migration is not the place to destroy the only surviving
record of what the previous configuration was.
"""

import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        """SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s""",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    if not _column_exists(cr, 'product_uom', 'available_in_pos'):
        _logger.info(
            "pos_product_packaging: no legacy POS packaging flags to carry over")
        return

    # A unit becomes available when any product had it enabled. Narrowing that
    # would silently switch off packagings people are already selling.
    cr.execute("""
        UPDATE uom_uom u
           SET available_in_pos = TRUE
         WHERE NOT COALESCE(u.available_in_pos, FALSE)
           AND EXISTS (SELECT 1 FROM product_uom pu
                        WHERE pu.uom_id = u.id
                          AND pu.available_in_pos)
    """)
    _logger.info("pos_product_packaging: enabled %s unit(s) for POS", cr.rowcount)
