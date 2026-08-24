import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Subscribe existing targets' responsible user.

    Same reason as the sales side: a tracking message is only written when the
    record has a follower, so targets predating the chatter would never show
    one.
    """
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    subscribed = 0
    for target in env['purchase.target'].search([]):
        partners = target.user_id.partner_id - target.message_partner_ids
        if partners:
            target.message_subscribe(partner_ids=partners.ids)
            subscribed += 1
    _logger.info(
        "eaglepub_purchase_target: subscribed followers on %s existing "
        "target(s).", subscribed)
