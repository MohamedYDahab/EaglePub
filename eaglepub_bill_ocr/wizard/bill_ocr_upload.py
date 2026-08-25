import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EaglepubBillOcrUpload(models.TransientModel):
    _name = 'eaglepub.bill.ocr.upload'
    _description = 'Digitise Vendor Bills'

    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string='Documents',
        required=True,
        help='PDFs or photographs of supplier invoices. One draft bill is '
             'created per document.',
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Journal',
        domain="[('type', '=', 'purchase')]",
        required=True,
        default=lambda self: self.env['account.journal'].search(
            [('type', '=', 'purchase'), ('company_id', '=', self.env.company.id)], limit=1),
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        required=True,
    )

    def action_digitise(self):
        """One draft bill per document.

        A document that cannot be read still produces its bill, flagged, with
        the file attached. Dropping it would be worse: the accountant would have
        to work out which of twenty invoices never arrived.
        """
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_('Add at least one document.'))

        Move = self.env['account.move']
        created = Move
        failures = 0

        for attachment in self.attachment_ids:
            move = Move.create({
                'move_type': 'in_invoice',
                'journal_id': self.journal_id.id,
                'company_id': self.company_id.id,
            })
            attachment.copy({
                'res_model': 'account.move',
                'res_id': move.id,
            })
            move.message_main_attachment_id = attachment.copy({
                'res_model': 'account.move',
                'res_id': move.id,
            })
            try:
                move._eaglepub_apply(attachment)
            except UserError as err:
                failures += 1
                move.sudo().write({
                    'eaglepub_ocr_state': 'error',
                    'eaglepub_ocr_message': str(err)[:200],
                })
                move.message_post(body=_(
                    'Could not digitise %(file)s: %(why)s',
                    file=attachment.name, why=err))
            created |= move

        action = {
            'type': 'ir.actions.act_window',
            'name': _('Digitised Bills'),
            'res_model': 'account.move',
            'domain': [('id', 'in', created.ids)],
            'view_mode': 'list,form',
            'context': {'default_move_type': 'in_invoice'},
        }
        if len(created) == 1:
            action.update(view_mode='form', res_id=created.id)
        if failures:
            _logger.info('bill ocr: %s of %s documents could not be read',
                         failures, len(self.attachment_ids))
        return action
