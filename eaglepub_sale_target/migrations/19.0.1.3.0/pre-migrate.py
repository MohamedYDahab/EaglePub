import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Drop target lines that were set in Amount.

    Targets are quantity only from 19.0.1.3.0. An amount line cannot be
    honestly converted -- amount divided by price is a guess about what the
    target meant -- so the lines are removed and the affected targets have to
    be re-entered. Recorded in the release note.
    """
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sale_target_line' AND column_name = 'target_type'
    """)
    if not cr.fetchone():
        return

    cr.execute("DELETE FROM sale_target_line WHERE target_type = 'amount'")
    _logger.warning(
        "eaglepub_sale_target: removed %s amount-based target line(s); "
        "targets are quantity only from 19.0.1.3.0 and these must be "
        "re-entered.", cr.rowcount)
