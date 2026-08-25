import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    eaglepub_ocr_state = fields.Selection(
        selection=[
            ('none', 'Not read'),
            ('done', 'Read'),
            ('check', 'Read - needs checking'),
            ('error', 'Could not read'),
        ],
        string='Digitisation',
        default='none',
        copy=False,
        readonly=True,
    )
    eaglepub_ocr_message = fields.Char(
        string='Digitisation Note',
        copy=False,
        readonly=True,
        help='Why the result needs checking, when it does.',
    )
    eaglepub_ocr_raw = fields.Text(
        string='Raw Extraction',
        copy=False,
        readonly=True,
        groups='account.group_account_invoice',
        help='Exactly what the reader returned, kept so a queried figure can be '
             'traced back to what was on the page.',
    )

    # ──────────────────────────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────────────────────────

    def action_eaglepub_digitise(self):
        """Read the attached document into this draft bill."""
        for move in self:
            if move.state != 'draft':
                raise UserError(_(
                    'Only a draft bill can be digitised. %s is already posted.',
                    move.display_name))
            attachment = move._eaglepub_source_attachment()
            if not attachment:
                raise UserError(_(
                    'Attach the supplier document to this bill first - a PDF or '
                    'a photograph of the invoice.'))
            move._eaglepub_apply(attachment)
        return True

    def _eaglepub_source_attachment(self):
        """The document to read: the main attachment, else the newest readable one."""
        self.ensure_one()
        main = self.message_main_attachment_id
        if main and main.mimetype in _supported_types():
            return main
        return self.env['ir.attachment'].search([
            ('res_model', '=', 'account.move'),
            ('res_id', '=', self.id),
            ('mimetype', 'in', list(_supported_types())),
        ], order='id desc', limit=1)

    def _eaglepub_apply(self, attachment):
        """Extract, then write. Failures are recorded on the bill, not swallowed."""
        self.ensure_one()
        service = self.env['eaglepub.bill.ocr.service']
        try:
            values, raw = service.extract(attachment)
        except UserError:
            # A user-actionable problem: let it surface as a dialog, but leave a
            # trace on the record so the state is not silently unchanged.
            self.sudo().write({'eaglepub_ocr_state': 'error'})
            raise
        except Exception as err:                       # noqa: BLE001 - see below
            # Anything else is a bug or an outage. The bill records that it
            # failed and the traceback goes to the log, rather than a stack
            # trace landing in an accountant's face.
            _logger.exception('bill ocr: extraction failed on move %s', self.id)
            self.sudo().write({
                'eaglepub_ocr_state': 'error',
                'eaglepub_ocr_message': str(err)[:200],
            })
            raise UserError(_(
                'Reading the document failed unexpectedly. The details are in '
                'the server log.')) from err

        ok, message = service.check_totals(values)
        self.write(self._eaglepub_prepare_values(values))
        self.sudo().write({
            'eaglepub_ocr_raw': raw,
            'eaglepub_ocr_state': 'done' if ok else 'check',
            'eaglepub_ocr_message': message or False,
        })
        self.message_post(body=_(
            'Digitised from %(file)s.%(note)s',
            file=attachment.name,
            note=(' ' + message) if message else '',
        ))

    # ──────────────────────────────────────────────────────────────
    # Mapping
    # ──────────────────────────────────────────────────────────────

    def _eaglepub_prepare_values(self, values):
        """Extracted values to account.move values.

        Only fields that were actually read are written, so re-reading a bill
        never blanks something a human has already corrected.
        """
        self.ensure_one()
        vals = {}

        partner = self._eaglepub_find_partner(values)
        if partner:
            vals['partner_id'] = partner.id

        if values.get('invoice_number'):
            vals['ref'] = values['invoice_number']
        if values.get('invoice_date'):
            vals['invoice_date'] = values['invoice_date']
        if values.get('due_date'):
            vals['invoice_date_due'] = values['due_date']

        currency = self._eaglepub_find_currency(values.get('currency'))
        if currency:
            vals['currency_id'] = currency.id

        lines = self._eaglepub_prepare_lines(values.get('lines') or [])
        if lines:
            # Replace rather than append: digitising twice should not double the
            # bill. Anything typed by hand beforehand is deliberately discarded,
            # which is why this only runs on drafts.
            vals['invoice_line_ids'] = [(5, 0, 0)] + lines

        return vals

    def _eaglepub_prepare_lines(self, lines):
        self.ensure_one()
        commands = []
        for line in lines:
            line_vals = {
                'name': line['description'],
                'quantity': line['quantity'],
                'price_unit': line['unit_price'],
            }
            tax = self._eaglepub_find_tax(line.get('tax_percent'))
            if tax:
                line_vals['tax_ids'] = [(6, 0, tax.ids)]
            commands.append((0, 0, line_vals))
        return commands

    def _eaglepub_find_partner(self, values):
        """VAT first, then an exact name, then a contains match.

        A vendor that cannot be matched is left empty on purpose. Creating one
        from a misread name quietly litters the address book, and an accountant
        picking the right vendor takes seconds.
        """
        Partner = self.env['res.partner']
        vat = values.get('vendor_vat')
        if vat:
            digits = ''.join(c for c in vat if c.isalnum())
            if digits:
                found = Partner.search(
                    [('vat', '!=', False), ('vat', 'ilike', digits[-8:])], limit=1)
                if found:
                    return found

        name = values.get('vendor_name')
        if not name:
            return Partner
        return (Partner.search([('name', '=ilike', name)], limit=1)
                or Partner.search([('name', 'ilike', name)], limit=1))

    def _eaglepub_find_currency(self, code):
        if not code:
            return self.env['res.currency']
        return self.env['res.currency'].with_context(active_test=False).search(
            [('name', '=', code.upper())], limit=1)

    def _eaglepub_find_tax(self, percent):
        """A purchase tax at that rate in this company, if one exists.

        No tax is applied when the rate is unknown or unmatched: an absent tax
        is visible to whoever checks the bill, a wrong one is not.
        """
        if percent in (None, False):
            return self.env['account.tax']
        return self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('amount_type', '=', 'percent'),
            ('amount', '>=', percent - 0.01),
            ('amount', '<=', percent + 0.01),
            ('company_id', '=', self.company_id.id),
        ], limit=1)


def _supported_types():
    from .bill_ocr_service import SUPPORTED_MIMETYPES
    return SUPPORTED_MIMETYPES
