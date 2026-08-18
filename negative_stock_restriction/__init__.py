from . import models

from .models.neg_stock_settings import PREFIX

# Settings that ship enabled. Anything meant to ship off is left absent,
# because that is how Odoo represents an unticked box.
DEFAULTS = {
    'enabled': 'True',
    'mode': 'hard',
    'stock_enabled': 'True',
    'pos_enabled': 'True',
    'so_enabled': 'True',
    'threshold': '5',
    'qty_type': 'available',
    'show_in_pos': 'True',
    'refresh_interval': '15',
    'manager_pin': '0000',
}


def post_init_hook(env):
    """Seed the initial settings on install.

    Deliberately not done with data.xml records. An ir.config_parameter row is
    deleted whenever the user unticks the matching box, and unlink() takes the
    ir.model.data row down with it -- which leaves the XML id dangling, so the
    next module upgrade tries to insert a key that already exists and dies on
    the unique constraint. Seeding here creates no XML ids to orphan.
    """
    ICP = env['ir.config_parameter'].sudo()
    for key, value in DEFAULTS.items():
        name = PREFIX + key
        if ICP.get_param(name) in (None, False, ''):
            ICP.set_param(name, value)
