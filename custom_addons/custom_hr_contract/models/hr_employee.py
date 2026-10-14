# Part of custom_hr_contract. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # === Vietnamese Citizen ID (CCCD) ===
    # Standard field `identification_id` (on hr.version, inherited) is reused
    # for the CCCD number. These fields add date/place of issue.
    id_card_date = fields.Date(
        string='ID Card Issue Date',
        groups='hr.group_hr_user',
        tracking=True,
        help="Date the Citizen ID card (CCCD) was issued.",
    )
    id_card_place = fields.Char(
        string='ID Card Issue Place',
        groups='hr.group_hr_user',
        tracking=True,
        default='Cục Cảnh sát QLHC về TTXH',
        help="Authority that issued the Citizen ID card.",
    )

    # === Permanent Address ===
    permanent_street = fields.Char(
        string='Permanent Street',
        groups='hr.group_hr_user',
        tracking=True,
    )
    permanent_ward = fields.Char(
        string='Permanent Ward',
        groups='hr.group_hr_user',
        tracking=True,
        help="Phường/Xã of the permanent address.",
    )
    permanent_district = fields.Char(
        string='Permanent District',
        groups='hr.group_hr_user',
        tracking=True,
        help="Quận/Huyện of the permanent address.",
    )
    permanent_city = fields.Char(
        string='Permanent City/Province',
        groups='hr.group_hr_user',
        tracking=True,
        help="Tỉnh/Thành phố of the permanent address.",
    )

    # === Temporary Address ===
    temporary_street = fields.Char(
        string='Temporary Street',
        groups='hr.group_hr_user',
        tracking=True,
    )
    temporary_ward = fields.Char(
        string='Temporary Ward',
        groups='hr.group_hr_user',
        tracking=True,
        help="Phường/Xã of the temporary address.",
    )
    temporary_district = fields.Char(
        string='Temporary District',
        groups='hr.group_hr_user',
        tracking=True,
        help="Quận/Huyện of the temporary address.",
    )
    temporary_city = fields.Char(
        string='Temporary City/Province',
        groups='hr.group_hr_user',
        tracking=True,
        help="Tỉnh/Thành phố of the temporary address.",
    )

    # === Tax & Insurance ===
    tax_id_number = fields.Char(
        string='Tax ID Number',
        groups='hr.group_hr_user',
        tracking=True,
        help="Mã số thuế thu nhập cá nhân.",
    )
    social_insurance_number = fields.Char(
        string='Social Insurance Number',
        groups='hr.group_hr_user',
        tracking=True,
        help="Số sổ bảo hiểm xã hội.",
    )

    # === Computed: Full Permanent Address ===
    permanent_address = fields.Char(
        string='Full Permanent Address',
        compute='_compute_permanent_address',
        help="Full concatenated permanent address for display/reports.",
    )
    # === Computed: Full Temporary Address ===
    temporary_address = fields.Char(
        string='Full Temporary Address',
        compute='_compute_temporary_address',
        help="Full concatenated temporary address for display/reports.",
    )

    @api.depends('permanent_street', 'permanent_ward', 'permanent_district', 'permanent_city')
    def _compute_permanent_address(self):
        for employee in self:
            parts = [
                p for p in [
                    employee.permanent_street,
                    employee.permanent_ward,
                    employee.permanent_district,
                    employee.permanent_city,
                ] if p
            ]
            employee.permanent_address = ', '.join(parts) if parts else False

    @api.depends('temporary_street', 'temporary_ward', 'temporary_district', 'temporary_city')
    def _compute_temporary_address(self):
        for employee in self:
            parts = [
                p for p in [
                    employee.temporary_street,
                    employee.temporary_ward,
                    employee.temporary_district,
                    employee.temporary_city,
                ] if p
            ]
            employee.temporary_address = ', '.join(parts) if parts else False
