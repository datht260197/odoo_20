# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class Employee(models.Model):
    _inherit = 'hr.employee'

    manager = fields.Boolean(string='Is a Manager')
    medic_exam = fields.Date(string='Medical Examination Date', groups='hr.group_hr_user')
    place_of_birth = fields.Char(string='Place of Birth', groups='hr.group_hr_user')
    children = fields.Integer(string='Number of Children', groups='hr.group_hr_user')
    vehicle = fields.Char(string='Company Vehicle', groups='hr.group_hr_user')
    vehicle_distance = fields.Integer(
        string='Home-Work Dist.',
        help='In kilometers',
        groups='hr.group_hr_user',
    )
    contract_ids = fields.One2many('hr.contract', 'employee_id', string='Contracts')
    contract_id = fields.Many2one(
        'hr.contract',
        compute='_compute_contract_id',
        string='Current Contract',
        help='Latest contract of the employee',
    )
    contracts_count = fields.Integer(
        compute='_compute_contracts_count',
        string='Contracts Count',
    )

    def _compute_contract_id(self):
        """Get the latest contract for each employee."""
        Contract = self.env['hr.contract']
        for employee in self:
            employee.contract_id = Contract.search(
                [('employee_id', '=', employee.id)],
                order='date_start desc',
                limit=1,
            )

    def _compute_contracts_count(self):
        """Count active contracts per employee in a batch-safe read_group query."""
        contract_data = self.env['hr.contract']._read_group(
            [('employee_id', 'in', self.ids)],
            ['employee_id'],
            ['__count'],
        )
        counts = {employee.id: count for employee, count in contract_data}
        for employee in self:
            employee.contracts_count = counts.get(employee.id, 0)

    def action_open_contract(self):
        """Open contracts action filtered for the current employee."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_contract.act_hr_employee_2_hr_contract')
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {
            'default_employee_id': self.id,
            'search_default_employee_id': self.id,
        }
        return action


class ContractType(models.Model):
    _name = 'hr.contract.type'
    _description = 'Contract Type'
    _order = 'sequence, id'

    name = fields.Char(string='Contract Type', required=True)
    sequence = fields.Integer(help='Gives the sequence when displaying a list of Contract.', default=10)


class Contract(models.Model):
    _name = 'hr.contract'
    _description = 'Contract'
    _inherit = ['mail.thread']

    name = fields.Char('Contract Reference', required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)
    type_id = fields.Many2one(
        'hr.contract.type',
        string='Contract Type',
        required=True,
        default=lambda self: self.env['hr.contract.type'].search([], limit=1),
    )
    job_id = fields.Many2one('hr.job', string='Job Position', tracking=True)
    date_start = fields.Date(
        'Start Date',
        required=True,
        default=fields.Date.today,
        help='Start date of the contract.',
        tracking=True,
    )
    date_end = fields.Date(
        'End Date',
        help="End date of the contract (if it's a fixed-term contract).",
        tracking=True,
    )
    trial_date_end = fields.Date(
        'End of Trial Period',
        help='End date of the trial period (if there is one).',
    )
    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        'Working Schedule',
        default=lambda self: self.env.company.resource_calendar_id.id,
    )
    wage = fields.Monetary(
        'Wage',
        required=True,
        help="Employee's monthly gross wage.",
        tracking=True,
    )
    advantages = fields.Text('Advantages')
    notes = fields.Text('Notes')
    state = fields.Selection([
        ('draft', 'New'),
        ('open', 'Running'),
        ('pending', 'To Renew'),
        ('close', 'Expired'),
        ('cancel', 'Cancelled'),
    ], string='Status', group_expand='_expand_states',
       tracking=True, help='Status of the contract', default='draft')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
    )
    permit_no = fields.Char('Work Permit No', related='employee_id.permit_no')
    visa_no = fields.Char('Visa No', related='employee_id.visa_no')
    visa_expire = fields.Date('Visa Expire Date', related='employee_id.visa_expire')

    word_template_id = fields.Many2one(
        'hr.contract.word.template',
        string='Word Template',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Select the Word (.docx) template used to generate the physical contract document.',
    )

    def _expand_states(self, states, domain, order=None):
        return [key for key, val in type(self).state.selection]

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.job_id = self.employee_id.job_id
            self.department_id = self.employee_id.department_id
            self.resource_calendar_id = self.employee_id.resource_calendar_id

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for contract in self:
            if contract.date_end and contract.date_start > contract.date_end:
                raise ValidationError(self.env._('Contract start date must be less than or equal to contract end date.'))

    @api.model
    def update_state(self):
        today = fields.Date.context_today(self)
        self.search([
            ('state', '=', 'open'),
            '|',
            '&',
            ('date_end', '<=', today + relativedelta(days=7)),
            ('date_end', '>=', today + relativedelta(days=1)),
            '&',
            ('visa_expire', '<=', today + relativedelta(days=60)),
            ('visa_expire', '>=', today + relativedelta(days=1)),
        ]).write({'state': 'pending'})

        self.search([
            ('state', 'in', ('open', 'pending')),
            '|',
            ('date_end', '<=', today + relativedelta(days=1)),
            ('visa_expire', '<=', today + relativedelta(days=1)),
        ]).write({'state': 'close'})

        return True

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'pending':
            return self.env.ref('hr_contract.mt_contract_pending')
        elif 'state' in init_values and self.state == 'close':
            return self.env.ref('hr_contract.mt_contract_close')
        return super()._track_subtype(init_values)

    def _build_docx_context(self):
        """Assemble a rich Jinja2 context mapping contract, employee, company, and Vietnamese localization fields."""
        self.ensure_one()
        employee = self.employee_id
        company = self.company_id or self.env.company

        # Employee Identification & Localization
        id_card_number = getattr(employee, 'identification_id', '') or ''
        id_card_date_val = getattr(employee, 'id_card_date', False)
        id_card_issue_date = id_card_date_val.strftime('%d/%m/%Y') if id_card_date_val else ''
        id_card_place = getattr(employee, 'id_card_place', '') or ''

        # Permanent Address
        perm_parts = [
            getattr(employee, f, '')
            for f in ('permanent_street', 'permanent_ward', 'permanent_district', 'permanent_city')
            if getattr(employee, f, '')
        ]
        permanent_address = ', '.join(perm_parts)

        # Temporary / Current Address
        temp_parts = [
            getattr(employee, f, '')
            for f in ('temporary_street', 'temporary_ward', 'temporary_district', 'temporary_city')
            if getattr(employee, f, '')
        ]
        current_address = ', '.join(temp_parts) if temp_parts else permanent_address

        # Trial period calculation (months)
        trial_period_months = 0
        if self.date_start and self.trial_date_end and self.trial_date_end >= self.date_start:
            delta = relativedelta(self.trial_date_end, self.date_start)
            trial_period_months = delta.months + (1 if delta.days > 15 else 0)

        # Vietnamese currency converter
        try:
            from odoo.addons.custom_hr_contract.tools.vietnamese_converter import num_to_words_vi
            wage_in_words = num_to_words_vi(int(self.wage or 0))
        except Exception:
            wage_in_words = f'{int(self.wage or 0):,} VND'

        # Allowances (from employee or custom_hr_contract if present)
        allowance_meal_val = getattr(employee, 'allowance_meal', 0) or 0
        allowance_transport_val = getattr(employee, 'allowance_transport', 0) or 0
        allowance_phone_val = getattr(employee, 'allowance_phone', 0) or 0
        allowance_housing_val = getattr(employee, 'allowance_housing', 0) or 0
        allowance_responsibility_val = getattr(employee, 'allowance_responsibility', 0) or 0

        # Gender / Sex display in Vietnamese
        gender_display = ''
        sex_val = getattr(employee, 'sex', '') or getattr(employee, 'gender', '')
        if sex_val:
            gender_map = {'male': 'Nam', 'female': 'Nữ', 'other': 'Khác'}
            gender_display = gender_map.get(sex_val, sex_val)

        # Representative display
        rep_partner = company.partner_id
        company_address = ', '.join([
            part for part in (
                company.street,
                company.street2,
                company.city,
                company.state_id.name if company.state_id else '',
                company.country_id.name if company.country_id else '',
            ) if part
        ])

        return {
            # Employee Information
            'employee_name': employee.name or '',
            'birthday': employee.birthday.strftime('%d/%m/%Y') if employee.birthday else '',
            'gender': gender_display,
            'id_card_number': id_card_number,
            'id_card_issue_date': id_card_issue_date,
            'id_card_place': id_card_place,
            'permanent_address': permanent_address,
            'current_address': current_address,
            'phone': employee.work_phone or employee.mobile_phone or '',
            'email': employee.work_email or '',
            'place_of_birth': employee.place_of_birth or '',

            # Contract Information
            'contract_name': self.name or '',
            'contract_type': self.type_id.name or '',
            'job_title': self.job_id.name or '',
            'department_name': self.department_id.name or '',
            'date_start': self.date_start.strftime('%d/%m/%Y') if self.date_start else '',
            'date_end': self.date_end.strftime('%d/%m/%Y') if self.date_end else 'Không xác định thời hạn',
            'trial_date_end': self.trial_date_end.strftime('%d/%m/%Y') if self.trial_date_end else '',
            'trial_period_months': trial_period_months,
            'working_schedule': self.resource_calendar_id.name if self.resource_calendar_id else '',

            # Compensation & Benefits
            'wage': f'{int(self.wage):,}' if self.wage else '0',
            'wage_in_words': wage_in_words,
            'currency': self.currency_id.name or 'VND',
            'allowance_meal': f'{int(allowance_meal_val):,}' if allowance_meal_val else '0',
            'allowance_transport': f'{int(allowance_transport_val):,}' if allowance_transport_val else '0',
            'allowance_phone': f'{int(allowance_phone_val):,}' if allowance_phone_val else '0',
            'allowance_housing': f'{int(allowance_housing_val):,}' if allowance_housing_val else '0',
            'allowance_responsibility': f'{int(allowance_responsibility_val):,}' if allowance_responsibility_val else '0',

            # Company Information
            'company_name': company.name or '',
            'company_address': company_address,
            'company_tax_id': company.vat or '',
            'company_phone': company.phone or '',
            'company_email': company.email or '',
            'company_representative': rep_partner.name if rep_partner else company.name,
            'representative_job_title': 'Người đại diện theo pháp luật',
        }

    def action_print_docx_contract(self):
        """Generate and download populated DOCX contract using docxtpl."""
        self.ensure_one()

        if not self.word_template_id:
            raise UserError(self.env._(
                'Vui lòng chọn Mẫu hợp đồng Word (Word Template) trước khi xuất tài liệu.\n'
                'Please select a Contract Word Template before exporting.'
            ))

        if not self.word_template_id.template_file:
            raise UserError(self.env._(
                'Mẫu hợp đồng "%s" chưa có file mẫu .docx được tải lên.\n'
                'The template "%s" does not contain an uploaded .docx file.'
            ) % (self.word_template_id.name, self.word_template_id.name))

        try:
            from docxtpl import DocxTemplate
        except ImportError:
            raise UserError(self.env._(
                'Thư viện docxtpl chưa được cài đặt trên máy chủ Odoo. Vui lòng cài đặt: pip install docxtpl\n'
                'The Python library "docxtpl" is not installed on the Odoo server.'
            ))

        # Open template stream safely whether BinaryValue, bytes, or base64
        raw_template = self.word_template_id.template_file
        if hasattr(raw_template, 'open'):
            template_stream = raw_template.open()
        elif hasattr(raw_template, 'content'):
            template_stream = io.BytesIO(raw_template.content)
        elif isinstance(raw_template, bytes):
            if raw_template.startswith(b'PK'):
                template_stream = io.BytesIO(raw_template)
            else:
                try:
                    decoded = base64.b64decode(raw_template, validate=True)
                    template_stream = io.BytesIO(decoded if decoded.startswith(b'PK') else raw_template)
                except Exception:
                    template_stream = io.BytesIO(raw_template)
        elif isinstance(raw_template, str):
            template_stream = io.BytesIO(base64.b64decode(raw_template))
        else:
            template_stream = io.BytesIO(bytes(raw_template))

        doc = DocxTemplate(template_stream)
        context = self._build_docx_context()

        # Render docx template with Jinja2 context
        doc.render(context)

        # Save to binary output stream
        output_stream = io.BytesIO()
        doc.save(output_stream)
        output_data = output_stream.getvalue()

        # Build clean ASCII filename for universal browser/OS download compatibility
        from odoo.tools import remove_accents
        raw_name = remove_accents(self.employee_id.name or 'NhanVien')
        safe_name = ''.join(c for c in raw_name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
        date_str = self.date_start.strftime('%Y%m%d') if self.date_start else fields.Date.today().strftime('%Y%m%d')
        filename = f'HDLD_{safe_name}_{date_str}.docx'

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'raw': output_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'type': 'binary',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
