# -*- coding: utf-8 -*-
"""Translate stored packaging references before the schema changes under them.

``pos.order.line.packaging_id`` used to point at ``product.uom`` and now points
at ``uom.uom``. Updating the module re-points the column's foreign key at
``uom_uom``, and Postgres will not create that constraint while existing rows
still hold ``product.uom`` ids - the upgrade fails outright on any database
that has sold a packaging.

So the translation has to happen here, in pre-migration, while the old ids are
still resolvable. The old foreign key is dropped first, because the rows would
otherwise be invalid under it the moment they are rewritten; Odoo creates the
new one during the update, once the data is already correct.

The companion post-migration script carries ``available_in_pos`` over, which
has to wait until the update has created that column on ``uom_uom``.
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

    # The legacy column is the marker that this database ran the product.uom
    # shape. Without it there is nothing to translate.
    if not _column_exists(cr, 'product_uom', 'available_in_pos'):
        _logger.info(
            "pos_product_packaging: no legacy product.uom configuration found, "
            "leaving stored packaging references alone")
        return

    # The old constraint points at product_uom and would reject the rewrite.
    cr.execute("""
        ALTER TABLE pos_order_line
         DROP CONSTRAINT IF EXISTS pos_order_line_packaging_id_fkey
    """)

    # References to link rows that no longer exist cannot be translated. Clear
    # them rather than leave an id that will resolve to an unrelated unit and
    # quietly print the wrong packaging on a reprinted receipt.
    cr.execute("""
        UPDATE pos_order_line
           SET packaging_id = NULL
         WHERE packaging_id IS NOT NULL
           AND packaging_id NOT IN (SELECT id FROM product_uom)
    """)
    orphaned = cr.rowcount

    # Translate the rest from the link row to the unit it pointed at.
    cr.execute("""
        UPDATE pos_order_line l
           SET packaging_id = pu.uom_id
          FROM product_uom pu
         WHERE l.packaging_id = pu.id
    """)
    _logger.info(
        "pos_product_packaging: remapped %s order line(s) to uom.uom, cleared "
        "%s unresolvable reference(s)", cr.rowcount, orphaned)
