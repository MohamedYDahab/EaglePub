# -*- coding: utf-8 -*-
from odoo import models, api


class SalesTargetReportParser(models.AbstractModel):
    _name = 'report.sales_team_target.report_sales_target'
    _description = 'Sales Target Report Parser'


    @api.model
    def _get_report_values(self, docids, data=None):
        if data and data.get('form'):
            wizard_id = data['form'].get('wizard_id')
            if wizard_id:
                wizard = self.env['sales.target.report.wizard'].browse(wizard_id)
            else:
                wizard = self.env['sales.target.report.wizard'].browse(docids)
        else:
            wizard = self.env['sales.target.report.wizard'].browse(docids)

        wizard.ensure_one()
        report_data = wizard._get_report_data()
        translations = wizard._get_translations()

        return {
            'doc_ids': wizard.ids,
            'doc_model': 'sales.target.report.wizard',
            'docs': wizard,
            'data': data,
            'report_data': report_data,
            'company': wizard.company_id,
            'translations': translations,
            'is_rtl': translations.get('is_rtl', False),
        }
