"""Shared readers for this module's ir.config_parameter settings.

They live in one place because the boolean semantics are easy to get wrong:
``set_param`` deletes a parameter when handed a falsy value, so an absent key
means "off" and must never fall back to "on". The switches that ship enabled
get their initial 'True' from data.xml instead.
"""

PREFIX = 'negative_stock_restriction.'
TRUE_VALUES = ('true', '1', 'yes', 'on')


def param(env, key, default=None):
    """Raw parameter value."""
    return env['ir.config_parameter'].sudo().get_param(PREFIX + key, default)


def flag(env, key):
    """Boolean setting; an absent parameter means off."""
    value = param(env, key)
    if value in (None, False, ''):
        return False
    return str(value).strip().lower() in TRUE_VALUES


def number(env, key, default):
    """Integer setting, falling back to ``default`` when unset or unparseable."""
    try:
        return int(float(param(env, key)))
    except (TypeError, ValueError):
        return default
