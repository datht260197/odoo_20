# Part of custom_hr_contract. See LICENSE file for full copyright and licensing details.

from odoo import api, models

from odoo.addons.custom_hr_contract.tools.vietnamese_converter import num_to_words_vi


class ReportLaborContract(models.AbstractModel):
    """QWeb report parser for Vietnamese Labor Contract (A4).

    Injects the ``num_to_words_vi`` converter function into the QWeb context,
    allowing the template to render any monetary amount as Vietnamese words.
    """

    _name = 'report.custom_hr_contract.report_labor_contract'
    _description = 'Vietnamese Labor Contract Report Parser'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.employee'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.employee',
            'docs': docs,
            'data': data or {},
            'num_to_words_vi': num_to_words_vi,
        }
