# -*- coding: utf-8 -*-
import logging
import threading
import requests

from odoo import models, fields, api, exceptions, _

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hằng số khóa tham số hệ thống (ir.config_parameter)
# ---------------------------------------------------------------------------
PARAM_TG_BOT_TOKEN = 'it_helpdesk.telegram_bot_token'
PARAM_TG_CHAT_ID   = 'it_helpdesk.telegram_chat_id'
PARAM_TG_ENABLED   = 'it_helpdesk.telegram_enabled'

# Tập hợp trạng thái "đã chốt" - không cho nhân viên thường sửa trường cốt lõi
_LOCKED_STATES = frozenset(['in_progress', 'done', 'cancelled'])

# Trường cốt lõi không được sửa khi phiếu đã chuyển trạng thái (với user thường)
_PROTECTED_FIELDS = frozenset(['title', 'description', 'employee_id', 'partner_id', 'request_type', 'category_id'])

# Trạng thái cuối - chỉ IT Manager hoặc assignee mới được chuyển vào
_FINAL_STATES = frozenset(['done', 'cancelled'])


class ItTicket(models.Model):
    """Model quản lý phiếu hỗ trợ IT chính (IT Ticket).
    
    Tích hợp:
    - Chuẩn giao diện Helpdesk Odoo 18 (Team, Assignee, Priority, Tags, Customer, Phone)
    - Liên kết tài sản CNTT (IT Asset) & lịch sử sửa chữa
    - Theo dõi chi phí & đơn vị sửa chữa ngoài (Partner / Vendor)
    - Tích hợp gửi phê duyệt chi phí (enterprise_approval)
    - Chatter & hoạt động nhắc việc
    - Thông báo tự động qua Telegram Bot
    """

    _name = 'it.ticket'
    _description = 'IT Support Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, name desc'
    _rec_name = 'name'
    _check_company_auto = True

    # =========================================================================
    # Thông tin định danh & Tiêu đề
    # =========================================================================

    name = fields.Char(
        string='Mã phiếu',
        readonly=True,
        copy=False,
        default='New',
        help='Mã phiếu tự động sinh khi tạo mới theo chuỗi tuần tự TICKET/YYYY/NNNN',
    )
    title = fields.Char(
        string='Tiêu đề yêu cầu',
        required=True,
        tracking=True,
        help='Tiêu đề mô tả sự cố hoặc yêu cầu hỗ trợ (Ví dụ: Máy in kẹt giấy, không vào được mạng...)',
    )
    description = fields.Html(
        string='Nội dung chi tiết',
        help='Mô tả chi tiết nội dung sự cố, thông báo lỗi hoặc yêu cầu',
    )

    # =========================================================================
    # Cấu trúc giao diện Odoo 18 Helpdesk (Hai cột chính)
    # =========================================================================

    # Cột 1: Helpdesk Team, Assigned to, Priority, Tags
    team_id = fields.Many2one(
        comodel_name='it.team',
        string='Helpdesk Team',
        default=lambda self: self._default_team_id(),
        tracking=True,
        help='Đội ngũ chuyên trách tiếp nhận và xử lý phiếu',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Assigned to',
        default=lambda self: self._default_user_id(),
        tracking=True,
        help='Người phụ trách kỹ thuật xử lý phiếu này',
    )
    priority = fields.Selection(
        selection=[
            ('0', 'Thấp (Low)'),
            ('1', 'Bình thường (Normal)'),
            ('2', 'Cao (High)'),
            ('3', 'Khẩn cấp (Urgent)'),
        ],
        string='Priority',
        default='1',
        tracking=True,
        help='Mức độ ưu tiên xử lý',
    )
    tag_ids = fields.Many2many(
        comodel_name='it.ticket.tag',
        relation='it_ticket_it_ticket_tag_rel',
        column1='ticket_id',
        column2='tag_id',
        string='Tags',
        help='Gán nhãn phân loại nhanh (Hardware, Software, Network, VIP...)',
    )

    # Cột 2: Customer, Phone & Thông tin người yêu cầu
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Công ty',
        default=lambda self: self.env.company,
        required=True,
        help='Công ty trực thuộc của phiếu hỗ trợ',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        default=lambda self: self._default_partner_id(),
        tracking=True,
        help='Khách hàng hoặc liên hệ đối tác gửi yêu cầu',
    )
    phone = fields.Char(
        string='Phone',
        compute='_compute_phone',
        store=True,
        readonly=False,
        help='Số điện thoại liên hệ của người gửi yêu cầu',
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Người yêu cầu (Nhân viên)',
        default=lambda self: self._default_employee(),
        tracking=True,
        help='Nhân viên nội bộ gửi yêu cầu hỗ trợ (tự động nhận diện từ user)',
    )
    department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Bộ phận / Phòng ban',
        compute='_compute_department_id',
        store=True,
        readonly=False,
        tracking=True,
        help='Phòng ban của người gửi yêu cầu (tự động nhận diện)',
    )
    location = fields.Char(
        string='Địa điểm',
        tracking=True,
        help='Vị trí làm việc hoặc phòng ban gặp sự cố (Ví dụ: Tầng 2, Chi nhánh Đà Nẵng, P. Kế toán...)',
    )
    assignee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Kỹ thuật viên phụ trách',
        tracking=True,
        help='Nhân viên IT phụ trách kỹ thuật (đồng bộ với user_id)',
    )

    # =========================================================================
    # Trạng thái xử lý (Statusbar & Kanban State)
    # =========================================================================

    kanban_state = fields.Selection(
        selection=[
            ('normal', 'Đang xử lý (In Progress)'),
            ('done', 'Sẵn sàng (Ready)'),
            ('blocked', 'Bị nghẽn (Blocked)'),
        ],
        string='Kanban State',
        default='normal',
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('new',         'New'),
            ('in_progress', 'In Progress'),
            ('waiting',     'On Hold'),
            ('done',        'Done'),
            ('cancelled',   'Cancelled'),
        ],
        string='Trạng thái',
        default='new',
        tracking=True,
        help='Tiến trình xử lý của phiếu hỗ trợ',
    )

    # =========================================================================
    # Tài sản CNTT & Sửa chữa (Asset & Repair Tracking)
    # =========================================================================

    asset_id = fields.Many2one(
        comodel_name='it.asset',
        string='Thiết bị CNTT liên quan',
        tracking=True,
        help='Gắn phiếu hỗ trợ với tài sản/thiết bị CNTT cụ thể đang gặp sự cố',
    )
    asset_serial = fields.Char(
        string='Serial / Service Tag',
        related='asset_id.serial_number',
        readonly=True,
    )
    asset_brand = fields.Char(
        string='Thương hiệu',
        related='asset_id.brand',
        readonly=True,
    )
    asset_model = fields.Char(
        string='Model',
        related='asset_id.model_name',
        readonly=True,
    )
    asset_employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Người đang sử dụng',
        related='asset_id.employee_id',
        readonly=True,
    )
    asset_department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Bộ phận sử dụng',
        related='asset_id.employee_id.department_id',
        readonly=True,
    )
    asset_warranty = fields.Date(
        string='Hạn bảo hành',
        related='asset_id.warranty_expiry',
        readonly=True,
    )
    asset_state = fields.Selection(
        string='Trạng thái thiết bị',
        related='asset_id.state',
        readonly=True,
    )

    # Theo dõi hình thức và chi phí sửa chữa
    has_repair = fields.Boolean(
        string='Có sửa chữa',
        compute='_compute_has_repair',
        store=True,
        readonly=False,
    )
    repair_type = fields.Selection(
        selection=[
            ('internal', 'Sửa chữa nội bộ (In-house)'),
            ('external', 'Gửi đơn vị sửa chữa ngoài (Vendor)'),
        ],
        string='Hình thức sửa chữa',
        default='internal',
        tracking=True,
    )
    repair_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Đơn vị sửa chữa ngoài',
        domain=[('is_company', '=', True)],
        tracking=True,
        help='Nhà cung cấp hoặc đơn vị dịch vụ sửa chữa bên ngoài',
    )
    repair_date_sent = fields.Date(
        string='Ngày gửi sửa chữa',
        tracking=True,
    )
    repair_date_expected = fields.Date(
        string='Ngày dự kiến nhận',
        tracking=True,
    )
    repair_date_received = fields.Date(
        string='Ngày thực tế nhận',
        tracking=True,
    )
    repair_cost = fields.Float(
        string='Chi phí sửa chữa (VNĐ)',
        digits=(16, 2),
        tracking=True,
        help='Chi phí dự kiến phát sinh cho việc sửa chữa thiết bị',
    )
    repair_actual_cost = fields.Float(
        string='Chi phí thực tế (VNĐ)',
        digits=(16, 2),
        tracking=True,
        help='Chi phí thực tế thanh toán cho việc sửa chữa thiết bị',
    )
    repair_status = fields.Selection(
        selection=[
            ('draft', 'Dự thảo / Chưa gửi'),
            ('sent', 'Đã gửi sửa chữa'),
            ('repaired', 'Đã sửa xong'),
            ('received', 'Đã nhận lại thiết bị'),
        ],
        string='Trạng thái sửa chữa',
        default='draft',
        tracking=True,
    )
    approval_state = fields.Selection(
        selection=[
            ('none', 'Không yêu cầu duyệt'),
            ('pending', 'Chờ duyệt chi phí'),
            ('approved', 'Đã duyệt chi phí'),
            ('rejected', 'Từ chối chi phí'),
        ],
        string='Duyệt chi phí',
        default='none',
        tracking=True,
    )
    approval_ref = fields.Char(
        string='Mã phiếu duyệt',
        readonly=True,
        copy=False,
        help='Mã định danh phiếu phê duyệt ngân sách/chi phí nếu có',
    )

    # =========================================================================
    # Phân loại dịch vụ & Mẫu công việc (Template)
    # =========================================================================

    request_type = fields.Selection(
        selection=[
            ('incident', 'Báo sự cố (Incident)'),
            ('service_request', 'Yêu cầu dịch vụ (Service Request)'),
            ('equipment_request', 'Yêu cầu cấp thiết bị'),
            ('software_request', 'Yêu cầu phần mềm'),
            ('other', 'Khác'),
        ],
        string='Loại yêu cầu',
        default='incident',
        required=True,
        tracking=True,
    )
    category_id = fields.Selection(
        selection=[
            ('network', 'Mạng / Wi-Fi'),
            ('computer', 'Máy tính bàn'),
            ('laptop', 'Laptop'),
            ('printer', 'Máy in / Máy scan'),
            ('camera', 'Camera an ninh'),
            ('software', 'Phần mềm / Ứng dụng'),
            ('odoo', 'Hệ thống Odoo'),
            ('email', 'Email doanh nghiệp'),
            ('account', 'Tài khoản & Phân quyền'),
            ('server', 'Máy chủ / Server'),
            ('hr_admin', 'HR & Admin'),
            ('accounting', 'Kế toán'),
            ('other', 'Khác / Thiết bị khác'),
        ],
        string='Danh mục',
        default='network',
        required=True,
        tracking=True,
    )
    template_id = fields.Many2one(
        comodel_name='it.ticket.template',
        string='Mẫu yêu cầu nhanh (Template)',
        help='Chọn mẫu để tự động điền tiêu đề, mô tả và mức độ ưu tiên vào phiếu',
    )

    # =========================================================================
    # Tài liệu & Đính kèm
    # =========================================================================

    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='it_ticket_ir_attachments_rel',
        column1='ticket_id',
        column2='attachment_id',
        string='Tệp đính kèm',
        help='Đính kèm ảnh chụp màn hình, tài liệu hoặc file liên quan đến yêu cầu',
    )
    attachment_count = fields.Integer(
        string='Số tài liệu',
        compute='_compute_attachment_count',
    )

    # =========================================================================
    # Thông tin thời gian & KPI
    # =========================================================================

    date_deadline = fields.Datetime(
        string='Hạn chót xử lý (Deadline)',
        tracking=True,
        help='Thời hạn cam kết hoàn thành xử lý sự cố',
    )
    resolution_note = fields.Html(
        string='Ghi chú / Giải pháp xử lý',
        help='Ghi chú giải pháp xử lý sự cố của kỹ thuật viên IT',
    )
    estimated_hours = fields.Float(
        string='Thời gian dự kiến (giờ)',
        digits=(6, 2),
    )
    actual_hours = fields.Float(
        string='Thời gian thực tế (giờ)',
        digits=(6, 2),
    )
    date_opened = fields.Datetime(
        string='Ngày tiếp nhận',
        default=fields.Datetime.now,
        readonly=True,
    )
    date_closed = fields.Datetime(
        string='Ngày hoàn thành',
        readonly=True,
    )
    color = fields.Integer(
        string='Màu Kanban',
        default=0,
    )

    # =========================================================================
    # Defaults & Computes
    # =========================================================================

    def _default_team_id(self):
        """Mặc định lấy đội ngũ hỗ trợ đầu tiên đang kích hoạt."""
        team = self.env['it.team'].search([('active', '=', True)], limit=1)
        return team or False

    def _default_employee(self):
        """Tự động nhận diện nhân viên ứng với user đang đăng nhập."""
        return self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1
        ) or False

    def _default_partner_id(self):
        """Mặc định lấy liên hệ của user hiện tại."""
        return self.env.user.partner_id or False

    def _default_user_id(self):
        """Chỉ gán người dùng hiện tại nếu họ thuộc nhóm IT (IT User / Manager).
        Đối với nhân viên thông thường tạo yêu cầu, để trống để đội ngũ IT tiếp nhận và phân bổ."""
        if self.env.user.has_group('it_helpdesk.group_it_user'):
            return self.env.user
        return False

    @api.depends('employee_id', 'employee_id.department_id')
    def _compute_department_id(self):
        """Tự động nhận diện phòng ban từ người yêu cầu."""
        for ticket in self:
            if ticket.employee_id and ticket.employee_id.department_id:
                ticket.department_id = ticket.employee_id.department_id
            elif not ticket.department_id:
                emp = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
                ticket.department_id = emp.department_id if emp else False

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Đếm số lượng tài liệu gắn với phiếu hỗ trợ."""
        for ticket in self:
            chatter_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', 'it.ticket'),
                ('res_id', '=', ticket.id),
            ]) if ticket.id else 0
            direct_count = len(ticket.attachment_ids)
            ticket.attachment_count = max(chatter_count, direct_count)

    @api.depends('repair_type', 'repair_cost', 'repair_partner_id', 'repair_status')
    def _compute_has_repair(self):
        """Xác định phiếu có phát sinh nội dung sửa chữa hay không."""
        for ticket in self:
            ticket.has_repair = bool(
                ticket.repair_cost > 0 or
                ticket.repair_partner_id or
                ticket.repair_type == 'external' or
                ticket.repair_status != 'draft'
            )

    @api.depends('partner_id.phone', 'employee_id.work_phone')
    def _compute_phone(self):
        """Tự động lấy số điện thoại từ Customer hoặc Employee."""
        for ticket in self:
            if not ticket.phone:
                if ticket.partner_id:
                    ticket.phone = ticket.partner_id.phone or False
                elif ticket.employee_id:
                    ticket.phone = ticket.employee_id.work_phone or False

    def _is_it_manager(self):
        """Kiểm tra user hiện tại có thuộc nhóm IT Manager không."""
        return self.env.user.has_group('it_helpdesk.group_it_manager')

    def _is_superuser(self):
        """Kiểm tra có phải superuser (admin kỹ thuật) không."""
        return self.env.su

    # =========================================================================
    # Smart Buttons & Action Helpers
    # =========================================================================

    def action_view_asset(self):
        """Mở chi tiết thiết bị CNTT liên quan."""
        self.ensure_one()
        if not self.asset_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Thiết bị CNTT - %s') % self.asset_id.name,
            'res_model': 'it.asset',
            'res_id': self.asset_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_repair_approval(self):
        """Mở phiếu duyệt chi phí hoặc thông báo trạng thái sửa chữa."""
        self.ensure_one()
        if self.approval_ref and 'approval.request' in self.env:
            app_req = self.env['approval.request'].search([('name', '=', self.approval_ref)], limit=1)
            if app_req:
                # Đồng bộ trạng thái duyệt về phiếu hỗ trợ
                if app_req.state == 'approved' and self.approval_state != 'approved':
                    self.write({'approval_state': 'approved'})
                elif app_req.state == 'rejected' and self.approval_state != 'rejected':
                    self.write({'approval_state': 'rejected'})
                elif app_req.state in ('draft', 'submitted') and self.approval_state != 'pending':
                    self.write({'approval_state': 'pending'})

                return {
                    'type': 'ir.actions.act_window',
                    'name': self.env._('Phiếu phê duyệt chi phí - %s', self.approval_ref),
                    'res_model': 'approval.request',
                    'res_id': app_req.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Thông tin sửa chữa'),
                'message': self.env._(
                    'Hình thức: %s | Chi phí: %s VNĐ | Trạng thái duyệt: %s',
                    dict(self._fields['repair_type'].selection).get(self.repair_type, self.repair_type),
                    f"{self.repair_cost:,.0f}",
                    dict(self._fields['approval_state'].selection).get(self.approval_state, self.approval_state),
                ),
                'type': 'info',
                'sticky': False,
            },
        }

    def action_view_attachments(self):
        """Mở danh sách tài liệu đính kèm của phiếu."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tài liệu đính kèm - %s') % self.name,
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,list,form',
            'domain': ['|', ('id', 'in', self.attachment_ids.ids), '&', ('res_model', '=', 'it.ticket'), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': 'it.ticket',
                'default_res_id': self.id,
            },
        }

    # =========================================================================
    # ORM Overrides
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """Tự động sinh mã phiếu tuần tự khi tạo mới."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('it.ticket') or 'New'

        tickets = super().create(vals_list)
        # Gắn kết các tệp đính kèm trực tiếp với model và record ID để đồng bộ chatter
        for ticket in tickets:
            if ticket.attachment_ids:
                ticket.attachment_ids.write({
                    'res_model': 'it.ticket',
                    'res_id': ticket.id,
                })
            ticket._schedule_telegram_notification()
        return tickets

    def write(self, vals):
        """Bảo vệ chống sửa trái phép khi phiếu đã chốt trạng thái."""
        if self._is_superuser():
            return super().write(vals)

        is_manager = self._is_it_manager()

        for record in self:
            # 1. Chặn sửa trường cốt lõi khi phiếu đã chốt
            if not is_manager and record.state in _LOCKED_STATES:
                protected_attempted = _PROTECTED_FIELDS & set(vals.keys())
                if protected_attempted:
                    field_labels = ', '.join(
                        record._fields[f].string
                        for f in protected_attempted
                        if f in record._fields
                    )
                    raise exceptions.UserError(_(
                        'Bạn không có quyền chỉnh sửa các trường: %(fields)s\n'
                        'Phiếu đang ở trạng thái "%(state)s" — '
                        'chỉ Quản lý IT mới được phép thay đổi.',
                        fields=field_labels,
                        state=dict(record._fields['state'].selection).get(record.state, record.state),
                    ))

            # 2. Kiểm soát chuyển trạng thái cuối sang done / cancelled
            new_state = vals.get('state')
            if new_state in _FINAL_STATES:
                assignee_uid = record.user_id.id if record.user_id else (
                    record.assignee_id.user_id.id if record.assignee_id else False
                )
                if not is_manager and self.env.uid != assignee_uid:
                    state_label = dict(record._fields['state'].selection).get(new_state, new_state)
                    raise exceptions.AccessError(_(
                        'Bạn không có quyền chuyển phiếu sang trạng thái "%(state)s".\n'
                        'Chỉ Quản lý IT hoặc Người phụ trách phiếu này mới được thực hiện.',
                        state=state_label,
                    ))

        return super().write(vals)

    # =========================================================================
    # Action methods (State Transitions & Approvals)
    # =========================================================================

    def action_set_in_progress(self):
        """Bắt đầu xử lý phiếu."""
        for record in self:
            record.write({'state': 'in_progress'})

    def action_set_waiting(self):
        """Tạm hoãn phiếu (On Hold)."""
        for record in self:
            record.write({'state': 'waiting'})

    def action_set_done(self):
        """Hoàn thành phiếu (Done)."""
        for record in self:
            record.write({
                'state': 'done',
                'date_closed': fields.Datetime.now(),
            })

    def action_set_cancelled(self):
        """Hủy phiếu (Cancelled)."""
        for record in self:
            record.write({'state': 'cancelled'})

    def action_reset_to_new(self):
        """Mở lại phiếu (Reset to New)."""
        if not self._is_it_manager() and not self._is_superuser():
            raise exceptions.AccessError(_('Chỉ Quản lý IT mới có thể mở lại phiếu đã hoàn thành hoặc hủy.'))
        for record in self:
            record.write({
                'state': 'new',
                'date_closed': False,
            })

    def action_request_repair_approval(self):
        """Tạo phiếu đề xuất phê duyệt chi phí sửa chữa qua enterprise_approval nếu có cài đặt."""
        self.ensure_one()
        if self.repair_cost <= 0:
            raise exceptions.UserError(self.env._('Chi phí sửa chữa phải lớn hơn 0 để gửi đề xuất phê duyệt.'))

        if 'approval.request' in self.env:
            category = self.env['approval.category'].search([('code', '=', 'PAYMENT')], limit=1)
            if not category:
                category = self.env['approval.category'].search([('has_amount', '=', 'required')], limit=1)
            if not category:
                category = self.env['approval.category'].search([], limit=1)

            asset_name = self.asset_id.name if self.asset_id else self.env._('(Không có)')
            vendor_name = self.repair_partner_id.name if self.repair_partner_id else self.env._('(Nội bộ)')

            req_vals = {
                'title': self.env._('Duyệt chi phí sửa chữa: %s (%s)', self.title, self.name),
                'category_id': category.id if category else False,
                'requester_id': self.env.user.id,
                'amount': self.repair_cost,
                'company_id': self.company_id.id if self.company_id else self.env.company.id,
                'description': (
                    f"<p><b>{self.env._('Yêu cầu phê duyệt chi phí sửa chữa thiết bị CNTT')}</b></p>"
                    f"<ul>"
                    f"<li><b>{self.env._('Mã phiếu hỗ trợ')}:</b> {self.name}</li>"
                    f"<li><b>{self.env._('Tiêu đề')}:</b> {self.title}</li>"
                    f"<li><b>{self.env._('Thiết bị')}:</b> {asset_name}</li>"
                    f"<li><b>{self.env._('Đơn vị sửa chữa')}:</b> {vendor_name}</li>"
                    f"<li><b>{self.env._('Chi phí dự kiến')}:</b> {self.repair_cost:,.0f} VNĐ</li>"
                    f"</ul>"
                ),
            }
            approval_req = self.env['approval.request'].create(req_vals)
            self.write({
                'approval_ref': approval_req.name,
                'approval_state': 'pending',
            })
            return {
                'type': 'ir.actions.act_window',
                'name': self.env._('Phiếu phê duyệt chi phí'),
                'res_model': 'approval.request',
                'res_id': approval_req.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            self.write({'approval_state': 'pending'})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': self.env._('Yêu cầu phê duyệt'),
                    'message': self.env._('Đã chuyển trạng thái sang Chờ duyệt chi phí (%s VNĐ).', f"{self.repair_cost:,.0f}"),
                    'type': 'success',
                    'sticky': False,
                },
            }

    # =========================================================================
    # Telegram Notification Methods
    # =========================================================================

    def _schedule_telegram_notification(self):
        """Lên lịch gửi thông báo Telegram trong thread riêng biệt."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_bool(PARAM_TG_ENABLED, default=False)
        if not enabled:
            return

        bot_token = ICP.get_str(PARAM_TG_BOT_TOKEN, default='')
        chat_id   = ICP.get_str(PARAM_TG_CHAT_ID, default='')

        if not bot_token or not chat_id:
            return

        # Soạn nội dung thông báo
        priority_stars = '⭐' * int(self.priority) if self.priority in ('1', '2', '3') else 'Bình thường'
        message_text = (
            f"🔔 <b>PHIẾU HỖ TRỢ IT MỚI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>Mã:</b> {self.name}\n"
            f"📌 <b>Tiêu đề:</b> {self.title}\n"
            f"👤 <b>Người yêu cầu:</b> {self.partner_id.name or self.employee_id.name or 'Chưa xác định'}\n"
            f"📞 <b>Điện thoại:</b> {self.phone or 'Không có'}\n"
            f"🏢 <b>Đội ngũ:</b> {self.team_id.name if self.team_id else 'Chưa phân công'}\n"
            f"⚡ <b>Độ ưu tiên:</b> {priority_stars}\n"
            f"💻 <b>Thiết bị:</b> {self.asset_id.name if self.asset_id else 'Không có'}\n"
        )

        def send_telegram():
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': message_text,
                    'parse_mode': 'HTML',
                }
                requests.post(url, json=payload, timeout=10)
            except Exception as e:
                _logger.warning("Lỗi gửi Telegram: %s", str(e))

        thread = threading.Thread(target=send_telegram, daemon=True)
        thread.start()

    def action_test_telegram_notification(self):
        """Nút test gửi thông báo Telegram cho Admin."""
        self.ensure_one()
        self._schedule_telegram_notification()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Thông báo Telegram'),
                'message': _('Đã kích hoạt gửi thử nghiệm thông báo qua Telegram.'),
                'type': 'info',
                'sticky': False,
            }
        }
