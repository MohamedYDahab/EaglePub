import base64
import json
import logging
import re
from datetime import datetime

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Formats a vision model can reasonably be handed. Anything else is refused up
# front rather than sent, paid for, and rejected at the far end.
SUPPORTED_MIMETYPES = (
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/webp',
)

# What the model is asked to return. Kept deliberately flat: every extra level
# of nesting is another thing a model can get subtly wrong.
EXTRACTION_SCHEMA = {
    'vendor_name': 'string or null',
    'vendor_vat': 'string or null',
    'invoice_number': 'string or null',
    'invoice_date': 'YYYY-MM-DD or null',
    'due_date': 'YYYY-MM-DD or null',
    'currency': 'ISO code such as USD, or null',
    'purchase_order': 'string or null',
    'lines': [{
        'description': 'string',
        'quantity': 'number',
        'unit_price': 'number',
        'tax_percent': 'number or null',
    }],
    'amount_untaxed': 'number or null',
    'amount_tax': 'number or null',
    'amount_total': 'number or null',
}

PROMPT = """You are reading a supplier invoice so it can be entered into an accounting system.

Return ONLY a JSON object, no prose and no code fences, matching this shape:
%s

Rules:
- Use null for anything not clearly printed on the document. Never guess.
- quantity and unit_price are the values as printed, before tax.
- tax_percent is the rate applied to that line, not the tax amount.
- Dates must be YYYY-MM-DD. If the format is ambiguous, prefer the one
  consistent with the other dates on the document.
- Do not invent a line that is not itemised. If the document shows only a
  total, return a single line describing it.
""" % json.dumps(EXTRACTION_SCHEMA, indent=2)


class EaglepubBillOcrService(models.AbstractModel):
    """Turns a document into a dict of bill values.

    Split from account.move on purpose: extraction is a service with an
    external dependency and its own failure modes, while the move should only
    ever deal in values it has already been handed.
    """

    _name = 'eaglepub.bill.ocr.service'
    _description = 'Vendor Bill OCR - extraction engine'

    # ──────────────────────────────────────────────────────────────
    # Configuration
    # ──────────────────────────────────────────────────────────────

    @api.model
    def _param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(
            'eaglepub_bill_ocr.%s' % key, default)

    @api.model
    def _provider(self):
        return self._param('provider', 'none')

    @api.model
    def _is_configured(self):
        provider = self._provider()
        if provider in ('none', ''):
            return False
        if provider == 'stub':
            return True
        return bool(self._param('api_key'))

    # ──────────────────────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────────────────────

    @api.model
    def extract(self, attachment):
        """Read one document. Returns (values, raw_text).

        Raises UserError for anything the user can act on - no key, wrong file
        type - and lets genuine failures propagate so they reach the log rather
        than being flattened into a shrug.
        """
        if not self._is_configured():
            raise UserError(_(
                'No document reader is configured yet. Set one up under '
                'Settings > Invoicing > Vendor Bill OCR, including the API key '
                'for the provider you want to use.'
            ))
        if attachment.mimetype not in SUPPORTED_MIMETYPES:
            raise UserError(_(
                '%(name)s is a %(kind)s, which cannot be read. Supply a PDF or a '
                'photograph (PNG, JPEG or WebP).',
                name=attachment.name, kind=attachment.mimetype or _('unknown type'),
            ))

        provider = self._provider()
        method = getattr(self, '_extract_%s' % provider, None)
        if method is None:
            raise UserError(_('Unknown document reader "%s".', provider))

        raw = method(attachment)
        return self._parse(raw), raw

    # ──────────────────────────────────────────────────────────────
    # Providers
    # ──────────────────────────────────────────────────────────────

    @api.model
    def _extract_stub(self, attachment):
        """A fixed response, for trying the pipeline without spending anything.

        Deliberately shipped rather than kept in tests: it lets a buyer install
        the module, press the button and see exactly what happens before they
        put a paid API key into it.
        """
        today = datetime.today()
        # Deliberately shaped like a real invoice - untidy quantities, a mixed
        # basket, a delivery charge and a tax line - so what a buyer sees when
        # they press the button resembles their own paperwork rather than a
        # placeholder. The figures are self-consistent so the arithmetic check
        # passes, which is itself part of what the sample demonstrates.
        return json.dumps({
            'vendor_name': 'Nile Office Supplies',
            'vendor_vat': 'EG204857716',
            'invoice_number': 'INV-2418',
            'invoice_date': today.strftime('%Y-%m-%d'),
            'due_date': None,
            'currency': None,
            'purchase_order': None,
            'lines': [
                {'description': 'Copier paper A4 80gsm, box of 5 reams',
                 'quantity': 12.0, 'unit_price': 24.50, 'tax_percent': 15.0},
                {'description': 'Toner cartridge, black, high yield',
                 'quantity': 3.0, 'unit_price': 89.00, 'tax_percent': 15.0},
                {'description': 'Delivery',
                 'quantity': 1.0, 'unit_price': 15.00, 'tax_percent': 15.0},
            ],
            'amount_untaxed': 576.00,
            'amount_tax': 86.40,
            'amount_total': 662.40,
        })

    @api.model
    def _extract_claude(self, attachment):
        return self._call_vision_api(
            attachment,
            url='https://api.anthropic.com/v1/messages',
            builder=self._payload_claude,
            reader=lambda d: d['content'][0]['text'],
            headers={
                'x-api-key': self._param('api_key'),
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
        )

    @api.model
    def _extract_openai(self, attachment):
        return self._call_vision_api(
            attachment,
            url='https://api.openai.com/v1/chat/completions',
            builder=self._payload_openai,
            reader=lambda d: d['choices'][0]['message']['content'],
            headers={
                'Authorization': 'Bearer %s' % self._param('api_key'),
                'Content-Type': 'application/json',
            },
        )

    @api.model
    def _payload_claude(self, attachment, model):
        data = base64.b64encode(attachment.raw).decode()
        kind = 'document' if attachment.mimetype == 'application/pdf' else 'image'
        return {
            'model': model,
            'max_tokens': 4096,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': kind,
                     'source': {'type': 'base64',
                                'media_type': attachment.mimetype,
                                'data': data}},
                    {'type': 'text', 'text': PROMPT},
                ],
            }],
        }

    @api.model
    def _payload_openai(self, attachment, model):
        data = base64.b64encode(attachment.raw).decode()
        return {
            'model': model,
            'max_tokens': 4096,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': PROMPT},
                    {'type': 'image_url',
                     'image_url': {'url': 'data:%s;base64,%s' % (attachment.mimetype, data)}},
                ],
            }],
        }

    @api.model
    def _call_vision_api(self, attachment, url, builder, reader, headers):
        import requests

        model = self._param('model') or self._default_model()
        timeout = int(self._param('timeout', '120') or 120)
        try:
            response = requests.post(
                url, headers=headers, json=builder(attachment, model), timeout=timeout)
        except requests.exceptions.Timeout:
            raise UserError(_(
                'The document reader did not answer within %s seconds. Large '
                'scans can take a while - raise the timeout in the settings, or '
                'try again.', timeout))
        except requests.exceptions.RequestException as err:
            raise UserError(_('Could not reach the document reader: %s', err))

        if response.status_code == 401:
            raise UserError(_('The document reader rejected the API key.'))
        if response.status_code == 429:
            raise UserError(_(
                'The document reader is rate limiting this account. Wait a '
                'moment and try again.'))
        if response.status_code >= 400:
            raise UserError(_(
                'The document reader returned an error (%(code)s): %(body)s',
                code=response.status_code, body=response.text[:400]))

        try:
            return reader(response.json())
        except (KeyError, IndexError, ValueError) as err:
            _logger.warning('bill ocr: unreadable response %s', response.text[:400])
            raise UserError(_(
                'The document reader answered in a shape this app does not '
                'recognise. The full response is in the server log. (%s)', err))

    @api.model
    def _default_model(self):
        return {
            'claude': 'claude-sonnet-4-5',
            'openai': 'gpt-4o',
        }.get(self._provider(), '')

    # ──────────────────────────────────────────────────────────────
    # Parsing
    # ──────────────────────────────────────────────────────────────

    @api.model
    def _parse(self, raw):
        """Model output to a validated dict.

        Models sometimes wrap JSON in prose or a code fence however firmly they
        are asked not to, so the object is located rather than assumed.
        """
        text = (raw or '').strip()
        if not text:
            raise UserError(_('The document reader returned nothing.'))

        fence = re.search(r'```(?:json)?\s*(.+?)\s*```', text, re.S)
        if fence:
            text = fence.group(1)
        else:
            start, end = text.find('{'), text.rfind('}')
            if start != -1 and end > start:
                text = text[start:end + 1]

        try:
            data = json.loads(text)
        except ValueError:
            _logger.warning('bill ocr: unparseable output %s', (raw or '')[:400])
            raise UserError(_(
                'The document reader did not return usable data for this file. '
                'It may be too blurred or too unusual a layout to read.'))
        if not isinstance(data, dict):
            raise UserError(_('The document reader returned data of the wrong shape.'))

        return {
            'vendor_name': self._clean_str(data.get('vendor_name')),
            'vendor_vat': self._clean_str(data.get('vendor_vat')),
            'invoice_number': self._clean_str(data.get('invoice_number')),
            'invoice_date': self._clean_date(data.get('invoice_date')),
            'due_date': self._clean_date(data.get('due_date')),
            'currency': self._clean_str(data.get('currency')),
            'purchase_order': self._clean_str(data.get('purchase_order')),
            'lines': self._clean_lines(data.get('lines')),
            'amount_untaxed': self._clean_float(data.get('amount_untaxed')),
            'amount_tax': self._clean_float(data.get('amount_tax')),
            'amount_total': self._clean_float(data.get('amount_total')),
        }

    @api.model
    def _clean_str(self, value):
        if value is None:
            return False
        text = str(value).strip()
        return text or False

    @api.model
    def _clean_float(self, value):
        if value in (None, '', False):
            return None
        try:
            source = str(value).strip()
            # Accountants write negatives in brackets. Stripping the brackets
            # without noticing turns a credit line into a charge, which is the
            # kind of error that reconciles to nothing a month later.
            negative = source.startswith('(') and source.endswith(')')

            # Tolerate "1.234,56" and "1,234.56" alike: strip everything that is
            # not a digit, separator or sign, then decide which separator is the
            # decimal one by which appears last.
            text = re.sub(r'[^\d,.\-]', '', source)
            if ',' in text and '.' in text:
                text = (text.replace(',', '') if text.rfind('.') > text.rfind(',')
                        else text.replace('.', '').replace(',', '.'))
            elif ',' in text:
                text = text.replace(',', '.')
            number = float(text)
            return -abs(number) if negative else number
        except (TypeError, ValueError):
            return None

    @api.model
    def _clean_date(self, value):
        text = self._clean_str(value)
        if not text:
            return False
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d.%m.%Y'):
            try:
                return datetime.strptime(text[:10], fmt).date()
            except ValueError:
                continue
        return False

    @api.model
    def _clean_lines(self, value):
        if not isinstance(value, list):
            return []
        lines = []
        for entry in value:
            if not isinstance(entry, dict):
                continue
            description = self._clean_str(entry.get('description'))
            qty = self._clean_float(entry.get('quantity'))
            price = self._clean_float(entry.get('unit_price'))
            if not description and price is None:
                continue
            lines.append({
                'description': description or _('Unnamed line'),
                'quantity': 1.0 if qty in (None, 0) else qty,
                'unit_price': price or 0.0,
                'tax_percent': self._clean_float(entry.get('tax_percent')),
            })
        return lines

    # ──────────────────────────────────────────────────────────────
    # Arithmetic check
    # ──────────────────────────────────────────────────────────────

    @api.model
    def check_totals(self, values, tolerance=0.02):
        """Compare the lines against the totals printed on the document.

        The single most useful check available: a model that misreads one digit
        of one line still produces a perfectly plausible bill, and only the
        arithmetic gives it away.

        Returns (ok, message).
        """
        stated = values.get('amount_untaxed')
        if stated is None:
            stated = values.get('amount_total')
        if stated is None or not values.get('lines'):
            return True, ''

        computed = sum((l['quantity'] or 0) * (l['unit_price'] or 0)
                       for l in values['lines'])
        gap = abs(computed - stated)
        if gap <= max(tolerance, abs(stated) * 0.005):
            return True, ''
        return False, _(
            'The lines add up to %(computed).2f but the document states '
            '%(stated).2f. Check the lines before posting.',
            computed=computed, stated=stated,
        )
