from odoo import models, api


class SaleTargetReportParser(models.AbstractModel):
    # Kept short deliberately: Odoo derives a table name from this and
    # PostgreSQL rejects identifiers over 63 characters.
    _name = 'report.eaglepub_sale_target.report_sales'
    _description = 'Sales Target Report Parser'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['sale.target.report.wizard'].browse(docids)
        wizard = wizards[:1]
        return {
            'doc_ids': docids,
            'doc_model': 'sale.target.report.wizard',
            'docs': wizards,
            'data': wizard._get_report_data() if wizard else {},
        }
