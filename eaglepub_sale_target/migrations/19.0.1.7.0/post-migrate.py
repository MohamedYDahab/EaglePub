import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Subscribe existing targets' salespeople and team leaders.

    Chatter was added in 19.0.1.7.0. Odoo only writes a tracking message when
    somebody follows the record, so targets that already existed would have
    kept an empty chatter forever -- the feature would look broken rather than
    new. Subscribing them once makes it live from the upgrade onward.
    """
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    subscribed = 0
    for target in env['sale.target'].search([]):
        partners = target.salesperson_id.partner_id | target.team_id.user_id.partner_id
        partners -= target.message_partner_ids
        if partners:
            target.message_subscribe(partner_ids=partners.ids)
            subscribed += 1
    _logger.info(
        "eaglepub_sale_target: subscribed followers on %s existing target(s).",
        subscribed)
