from odoo import api, fields, models

PREFIX = 'eaglepub_bill_ocr.'
KEYS = ('provider', 'api_key', 'model', 'timeout')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    eaglepub_ocr_provider = fields.Selection(
        selection=[
            ('none', 'Off'),
            ('claude', 'Claude (Anthropic)'),
            ('openai', 'OpenAI'),
            ('stub', 'Sample data (no key needed)'),
        ],
        string='Document Reader',
        default='none',
        config_parameter=PREFIX + 'provider',
        help='Which vision model reads your documents. Sample data fills a bill '
             'with fixed values so you can see the flow before paying for a key.',
    )
    eaglepub_ocr_api_key = fields.Char(
        string='API Key',
        config_parameter=PREFIX + 'api_key',
        help='Your own key with the provider. Stored server-side and never sent '
             'to the browser.',
    )
    eaglepub_ocr_model = fields.Char(
        string='Model',
        config_parameter=PREFIX + 'model',
        help='Leave empty to use a sensible default for the chosen provider.',
    )
    eaglepub_ocr_timeout = fields.Integer(
        string='Timeout (seconds)',
        default=120,
        config_parameter=PREFIX + 'timeout',
        help='Large scans take longer. Raise this if documents time out.',
    )
