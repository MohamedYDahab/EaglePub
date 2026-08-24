from odoo import api, models


class EaglepubPosReport(models.AbstractModel):
    _name = 'report.eaglepub_pos_reports.report_pos'
    _description = 'POS Reports Pack - PDF renderer'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Hand the template everything pre-computed.

        QWeb refuses to call methods whose names begin with an underscore, so
        the figures are assembled here rather than in the template.
        """
        wizards = self.env['eaglepub.pos.report.wizard'].browse(docids)
        wiz = wizards[:1]
        tr = wiz._get_translations()
        return {
            'doc_ids': docids,
            'doc_model': 'eaglepub.pos.report.wizard',
            'docs': wizards,
            'wiz': wiz,
            'tr': tr,
            'columns': wiz._columns(tr),
            'report_data': wiz._get_report_data(),
            'totals_keys': wiz._totalled_keys(),
        }
