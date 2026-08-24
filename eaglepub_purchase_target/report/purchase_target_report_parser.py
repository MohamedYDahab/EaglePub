from odoo import models, api


class PurchaseTargetReportParser(models.AbstractModel):
    _name = 'report.eaglepub_purchase_target.report_purchase_target'
    _description = 'Purchase Target Report Parser'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['purchase.target.report.wizard'].browse(docids)
        wizard = wizards[:1]
        return {
            'doc_ids': docids,
            'doc_model': 'purchase.target.report.wizard',
            'docs': wizards,
            'data': wizard._get_report_data() if wizard else {},
        }
