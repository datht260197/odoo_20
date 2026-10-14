# -*- coding: utf-8 -*-
import hashlib
import secrets
from datetime import timedelta
from odoo import models, fields, api, exceptions, _


# Các trường cốt lõi không được phép chỉnh sửa khi phiếu đã gửi duyệt hoặc hoàn tất
_PROTECTED_REQUEST_FIELDS = frozenset([
    'title', 'description', 'category_id', 'amount',
    'date_start', 'date_end', 'location', 'requester_id', 'priority'
])


class ApprovalRequest(models.Model):
    """Mô hình Phiếu yêu cầu phê duyệt doanh nghiệp (Approval Request)."""

    _name = 'approval.request'
    _description = 'Yêu cầu phê duyệt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_submitted desc, id desc'
    _rec_name = 'name'
    _check_company_auto = True

    # =========================================================================
    # 1. Định danh & Phân loại
    # =========================================================================

    name = fields.Char(
        string='Mã yêu cầu',
        readonly=True,
        copy=False,
        default='New',
        tracking=True,
        help='Mã yêu cầu tự động sinh theo mẫu REQ/YYYY/NNNN',
    )
    title = fields.Char(
        string='Tiêu đề phê duyệt',
        required=True,
        tracking=True,
        help='Tóm tắt ngắn gọn nội dung yêu cầu (ví dụ: Đi công tác Hà Nội, Tạm ứng công tác phí)',
    )
    category_id = fields.Many2one(
        comodel_name='approval.category',
        string='Loại phê duyệt',
        required=True,
        tracking=True,
        help='Loại yêu cầu / danh mục luồng phê duyệt',
    )
    category_code = fields.Char(
        string='Mã danh mục',
        related='category_id.code',
        store=True,
    )
    has_amount = fields.Selection(
        related='category_id.has_amount',
        string='Có trường số tiền',
    )
    has_date = fields.Selection(
        related='category_id.has_date',
        string='Có trường thời gian',
    )
    has_location = fields.Selection(
        related='category_id.has_location',
        string='Có trường địa điểm',
    )
    category_image = fields.Binary(
        string='Hình ảnh danh mục',
        related='category_id.image',
        readonly=True,
    )

    # =========================================================================
    # 2. Nhân sự & Đơn vị
    # =========================================================================

    requester_id = fields.Many2one(
        comodel_name='res.users',
        string='Người tạo yêu cầu',
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
        help='Tài khoản người dùng tạo và gửi yêu cầu phê duyệt',
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Nhân viên',
        compute='_compute_employee_info',
        store=True,
        readonly=False,
        help='Hồ sơ nhân sự liên kết với người tạo yêu cầu',
    )
    department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Phòng ban',
        compute='_compute_employee_info',
        store=True,
        help='Phòng ban của nhân viên',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Công ty',
        default=lambda self: self.env.company,
        required=True,
    )

    # Người duyệt
    approver_id = fields.Many2one(
        comodel_name='res.users',
        string='Người phê duyệt',
        tracking=True,
        help='Người chịu trách nhiệm xem xét và phê duyệt yêu cầu này',
    )
    approver_ids = fields.One2many(
        comodel_name='approval.approver',
        inverse_name='request_id',
        string='Danh sách người duyệt',
    )
    current_stage_id = fields.Many2one(
        comodel_name='approval.workflow.stage',
        string='Bước duyệt hiện tại',
        tracking=True,
    )

    # =========================================================================
    # 3. Trạng thái & Mức độ ưu tiên
    # =========================================================================

    state = fields.Selection(
        selection=[
            ('draft', 'Chờ nộp'),
            ('submitted', 'Chờ duyệt'),
            ('approved', 'Đã duyệt'),
            ('rejected', 'Từ chối'),
            ('cancelled', 'Đã hủy'),
        ],
        string='Trạng thái',
        default='draft',
        required=True,
        tracking=True,
        help='Trạng thái xử lý của yêu cầu phê duyệt',
    )
    priority = fields.Selection(
        selection=[
            ('0', 'Thấp'),
            ('1', 'Bình thường'),
            ('2', 'Cao'),
            ('3', 'Khẩn cấp'),
        ],
        string='Độ ưu tiên',
        default='1',
        tracking=True,
    )

    # =========================================================================
    # 4. Nội dung chi tiết & Thông số đặc thù
    # =========================================================================

    description = fields.Html(
        string='Nội dung mô tả',
        help='Lý do chi tiết, tài liệu liên quan hoặc nội dung đề xuất',
    )
    amount = fields.Monetary(
        string='Số tiền',
        currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.company.currency_id,
    )
    date_start = fields.Datetime(
        string='Thời gian bắt đầu',
        tracking=True,
    )
    date_end = fields.Datetime(
        string='Thời gian kết thúc',
        tracking=True,
    )
    location = fields.Char(
        string='Địa điểm / Lộ trình',
        tracking=True,
        help='Địa điểm công tác, địa chỉ giao hàng hoặc lộ trình điều xe',
    )

    # =========================================================================
    # 5. Theo dõi xử lý & Lý do từ chối
    # =========================================================================

    date_submitted = fields.Datetime(
        string='Thời gian gửi duyệt',
        readonly=True,
    )
    date_confirmed = fields.Datetime(
        string='Thời gian xử lý',
        readonly=True,
    )
    confirmed_by = fields.Many2one(
        comodel_name='res.users',
        string='Người quyết định',
        readonly=True,
    )
    rejection_reason = fields.Text(
        string='Lý do từ chối',
        readonly=True,
        tracking=True,
    )

    # Nhật ký
    history_ids = fields.One2many(
        comodel_name='approval.history',
        inverse_name='request_id',
        string='Nhật ký phê duyệt',
    )

    # Quyền hạn tính toán cho user hiện tại
    can_approve = fields.Boolean(
        string='Có quyền duyệt',
        compute='_compute_user_permissions',
    )
    can_reject = fields.Boolean(
        string='Có quyền từ chối',
        compute='_compute_user_permissions',
    )
    attachment_number = fields.Integer(
        string='Tài liệu đính kèm',
        compute='_compute_attachment_number',
    )

    # =========================================================================
    # Compute & Onchange Methods
    # =========================================================================

    @api.depends('requester_id')
    def _compute_employee_info(self):
        """Tự động tìm kiếm nhân viên và phòng ban từ user gửi yêu cầu."""
        Employee = self.env['hr.employee']
        for record in self:
            if record.requester_id:
                emp = Employee.search([('user_id', '=', record.requester_id.id)], limit=1)
                record.employee_id = emp
                record.department_id = emp.department_id if emp else False
            else:
                record.employee_id = False
                record.department_id = False

    def _compute_attachment_number(self):
        """Đếm số tệp tài liệu đính kèm vào phiếu."""
        attachment_data = self.env['ir.attachment']._read_group(
            domain=[('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            groupby=['res_id'],
            aggregates=['__count'],
        )
        data_map = {res_id: count for res_id, count in attachment_data}
        for rec in self:
            rec.attachment_number = data_map.get(rec.id, 0)

    @api.depends('state', 'approver_id', 'approver_ids.user_id', 'approver_ids.status')
    def _compute_user_permissions(self):
        """Xác định user hiện tại có thẩm quyền duyệt/từ chối phiếu hay không."""
        is_manager = self.env.user.has_group('enterprise_approval.group_approval_manager')
        current_uid = self.env.uid

        for rec in self:
            if rec.state == 'submitted':
                approver_uids = rec.approver_ids.mapped('user_id').ids
                is_authorized_approver = (
                    is_manager or
                    rec.approver_id.id == current_uid or
                    current_uid in approver_uids
                )
                rec.can_approve = is_authorized_approver
                rec.can_reject = is_authorized_approver
            else:
                rec.can_approve = False
                rec.can_reject = False

    @api.onchange('category_id')
    def _onchange_category_id(self):
        """Khi chọn danh mục, tự động đề xuất người phê duyệt hoặc quản lý trực tiếp."""
        if self.category_id:
            approvers = self.env['res.users']
            # Nếu danh mục cấu hình duyệt bởi Quản lý trực tiếp
            if self.category_id.manager_approval and self.employee_id and self.employee_id.parent_id and self.employee_id.parent_id.user_id:
                approvers |= self.employee_id.parent_id.user_id
            # Nếu có người duyệt mặc định từ danh mục
            if self.category_id.approver_id:
                approvers |= self.category_id.approver_id
            for stage in self.category_id.stage_ids:
                if stage.approver_id:
                    approvers |= stage.approver_id

            if approvers:
                self.approver_id = approvers[0]
                existing_uids = [a.user_id.id for a in self.approver_ids if a.user_id]
                lines = []
                for user in approvers:
                    if user.id not in existing_uids:
                        lines.append((0, 0, {'user_id': user.id, 'status': 'new'}))
                if lines:
                    self.approver_ids = lines

    # =========================================================================
    # ORM Overrides & Security Protection
    # =========================================================================

    # =========================================================================
    # ORM Overrides & Security Protection
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """Sinh mã tuần tự tự động khi tạo phiếu và lưu vết khởi tạo."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('approval.request') or 'New'

        requests = super().create(vals_list)
        for request in requests:
            request._log_history('draft', request.env._('Khởi tạo yêu cầu phê duyệt'))
        return requests

    def write(self, vals):
        """Ngăn chặn người dùng thường sửa trường cốt lõi khi phiếu đã gửi duyệt hoặc đã chốt."""
        is_manager = self.env.user.has_group('enterprise_approval.group_approval_manager')

        for rec in self:
            if not is_manager and rec.state in ('submitted', 'approved', 'rejected'):
                attempted = _PROTECTED_REQUEST_FIELDS & set(vals.keys())
                if attempted:
                    field_names = ', '.join(rec._fields[f].string for f in attempted if f in rec._fields)
                    raise exceptions.UserError(rec.env._(
                        'Không thể sửa các trường sau: %(fields)s!\n'
                        'Yêu cầu "%(code)s" hiện đang ở trạng thái "%(state)s".',
                        fields=field_names,
                        code=rec.name,
                        state=dict(rec._fields['state'].selection).get(rec.state, rec.state),
                    ))

        return super().write(vals)

    def unlink(self):
        """Chỉ cho phép xóa phiếu khi đang ở trạng thái Chờ nộp hoặc Đã hủy."""
        is_manager = self.env.user.has_group('enterprise_approval.group_approval_manager')
        for rec in self:
            if not is_manager and rec.state not in ('draft', 'cancelled'):
                raise exceptions.UserError(rec.env._(
                    'Bạn chỉ có thể xóa các yêu cầu ở trạng thái "Nháp" hoặc "Đã hủy".'
                ))
        return super().unlink()

    # =========================================================================
    # Workflow Actions
    # =========================================================================

    def action_submit(self):
        """Gửi phiếu yêu cầu đi phê duyệt."""
        self.check_access('write')
        for rec in self:
            if rec.state != 'draft':
                raise exceptions.UserError(rec.env._('Chỉ các yêu cầu ở trạng thái "Nháp" mới có thể nộp duyệt.'))

            # Validate required fields based on category configuration
            if rec.category_id.has_amount == 'required' and not rec.amount:
                raise exceptions.ValidationError(rec.env._('Vui lòng nhập Số tiền cho loại phê duyệt "%s".', rec.category_id.name))
            if rec.category_id.has_date == 'required' and not rec.date_start:
                raise exceptions.ValidationError(rec.env._('Vui lòng nhập Thời gian cho loại phê duyệt "%s".', rec.category_id.name))
            if rec.category_id.has_location == 'required' and not rec.location:
                raise exceptions.ValidationError(rec.env._('Vui lòng nhập Địa điểm cho loại phê duyệt "%s".', rec.category_id.name))

            # Ensure an approver is assigned
            if not rec.approver_id:
                # Find from first stage or category default
                stages = rec.category_id.stage_ids.sorted('sequence')
                if stages and stages[0].approver_id:
                    rec.approver_id = stages[0].approver_id
                    rec.current_stage_id = stages[0]
                elif rec.category_id.approver_id:
                    rec.approver_id = rec.category_id.approver_id
                elif rec.employee_id and rec.employee_id.parent_id and rec.employee_id.parent_id.user_id:
                    rec.approver_id = rec.employee_id.parent_id.user_id

            if not rec.approver_id:
                raise exceptions.UserError(rec.env._(
                    'Chưa chỉ định người phê duyệt! Vui lòng chọn người duyệt trước khi nộp.'
                ))

            # Đồng bộ danh sách người duyệt nếu chưa có dòng nào
            if not rec.approver_ids and rec.approver_id:
                self.env['approval.approver'].create({
                    'request_id': rec.id,
                    'user_id': rec.approver_id.id,
                    'status': 'new',
                })

            # Change status
            rec.write({
                'state': 'submitted',
                'date_submitted': fields.Datetime.now(),
            })

            # Log action
            rec._log_history('submit', rec.env._('Đã gửi yêu cầu tới %s', rec.approver_id.name))

            # Notify via Chatter and schedule activity
            rec.message_post(
                body=rec.env._('<b>Phiếu yêu cầu phê duyệt đã được gửi đi.</b><br/>Người duyệt được giao: <b>%s</b>', rec.approver_id.name),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
            rec._schedule_approver_activity()

    def action_approve(self):
        """Phê duyệt yêu cầu qua xác thực 2FA OTP chữ ký số."""
        self.ensure_one()
        self.check_access('write')
        is_manager = self.env.user.has_group('enterprise_approval.group_approval_manager')
        current_uid = self.env.uid

        if self.state != 'submitted':
            raise exceptions.UserError(self.env._('Chỉ những yêu cầu ở trạng thái Chờ duyệt mới có thể phê duyệt.'))

        # Check approval permission
        approver_uids = self.approver_ids.mapped('user_id').ids
        if not is_manager and self.approver_id.id != current_uid and current_uid not in approver_uids:
            raise exceptions.AccessError(self.env._('Bạn không có quyền phê duyệt yêu cầu này.'))

        # Ensure approver line exists
        approver = self.approver_ids.filtered(lambda a: a.user_id.id == current_uid)
        if not approver:
            approver = self.env['approval.approver'].create({
                'request_id': self.id,
                'user_id': current_uid,
                'status': 'new',
            })
        else:
            approver = approver[0]

        # Determine corporate email: env.user.email or employee_id.work_email
        reviewer_email = self.env.user.email or (self.env.user.employee_id and self.env.user.employee_id.work_email)
        if not reviewer_email:
            raise exceptions.UserError(self.env._(
                'Người dùng "%(user)s" chưa được cấu hình địa chỉ email công vụ. '
                'Cần có email để nhận mã OTP xác thực ký số 2FA.',
                user=self.env.user.name,
            ))

        # Generate cryptographically secure 6-digit numeric OTP
        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = hashlib.sha256(otp_code.encode('utf-8')).hexdigest()
        otp_expiry = fields.Datetime.now() + timedelta(minutes=10)

        # Transmit OTP via mail template
        template = self.env.ref('enterprise_approval.mail_template_approval_otp', raise_if_not_found=False)
        if template:
            template.with_context(
                otp_code=otp_code,
                otp_expiry=otp_expiry,
                recipient_email=reviewer_email,
                approver_name=self.env.user.name,
            ).send_mail(self.id, force_send=True)

        # Create wizard and return action
        wizard = self.env['approval.signature.otp.wizard'].create({
            'request_id': self.id,
            'approver_id': approver.id,
            'otp_code_hash': otp_hash,
            'otp_expiry': otp_expiry,
        })
        return {
            'name': self.env._('Xác thực chữ ký số OTP'),
            'type': 'ir.actions.act_window',
            'res_model': 'approval.signature.otp.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def _process_approval_after_otp(self, approver, comment=None):
        """Complete the approval workflow step after successful OTP verification."""
        self.ensure_one()
        self.check_access('write')
        approver.write({'status': 'approved'})

        # Kiểm tra nếu còn cấp duyệt tiếp theo trong luồng
        stages = self.category_id.stage_ids.sorted('sequence')
        next_stage = False
        if stages and self.current_stage_id:
            later_stages = stages.filtered(lambda s: s.sequence > self.current_stage_id.sequence)
            if later_stages:
                next_stage = later_stages[0]

        if next_stage:
            # Chuyển tiếp sang bước duyệt sau
            next_approver = next_stage.approver_id or self.approver_id
            self.write({
                'current_stage_id': next_stage.id,
                'approver_id': next_approver.id,
            })
            # Bổ sung approver tiếp theo nếu chưa có
            if next_approver.id not in self.approver_ids.mapped('user_id').ids:
                self.env['approval.approver'].create({
                    'request_id': self.id,
                    'user_id': next_approver.id,
                    'status': 'new',
                })
            log_msg = self.env._(
                'Bước "%(prev)s" đã được phê duyệt bằng chữ ký số 2FA. Đã chuyển tiếp tới: "%(next)s" (%(approver)s)',
                prev=self.current_stage_id.name,
                next=next_stage.name,
                approver=next_approver.name,
            )
            if comment:
                log_msg += f"\n{self.env._('Ý kiến:')} {comment}"
            self._log_history('approve', log_msg)
            self.message_post(
                body=self.env._('<b>Bước duyệt đã được phê duyệt bằng chữ ký số 2FA OTP.</b> Chuyển tiếp tới bước duyệt: <b>%s</b>', next_stage.name),
            )
            self._schedule_approver_activity()
        else:
            # Final approval
            signer_user = approver.user_id or self.env.user
            self.write({
                'state': 'approved',
                'date_confirmed': fields.Datetime.now(),
                'confirmed_by': signer_user.id,
            })
            log_msg = self.env._('Phiếu yêu cầu đã được phê duyệt với chữ ký số 2FA OTP.')
            if comment:
                log_msg += f"\n{self.env._('Ý kiến:')} {comment}"
            self._log_history('approve', log_msg)

            # Close pending activity
            self.activity_feedback(['mail.mail_activity_data_todo'])

            # Notify via Chatter
            self.message_post(
                body=self.env._('🎉 <b>YÊU CẦU ĐÃ ĐƯỢC PHÊ DUYỆT BẰNG CHỮ KÝ SỐ 2FA!</b><br/>Người phê duyệt: <b>%s</b> (Mã băm: <code>%s</code>)', signer_user.name, approver.signature_hash or ''),
                message_type='notification',
            )

    def action_print_slip(self):
        """Mở cửa sổ cấu hình in phiếu phê duyệt A4."""
        self.ensure_one()
        return {
            'name': self.env._('In phiếu phê duyệt'),
            'type': 'ir.actions.act_window',
            'res_model': 'approval.slip.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
            },
        }


    def action_reject(self):
        """Mở cửa sổ nhập lý do từ chối."""
        self.ensure_one()
        self.check_access('write')
        is_manager = self.env.user.has_group('enterprise_approval.group_approval_manager')
        current_uid = self.env.uid

        if self.state != 'submitted':
            raise exceptions.UserError(self.env._('Chỉ có thể từ chối các yêu cầu ở trạng thái Chờ duyệt.'))

        approver_uids = self.approver_ids.mapped('user_id').ids
        if not is_manager and self.approver_id.id != current_uid and current_uid not in approver_uids:
            raise exceptions.AccessError(self.env._('Bạn không có quyền từ chối yêu cầu này.'))

        return {
            'name': self.env._('Từ chối yêu cầu phê duyệt'),
            'type': 'ir.actions.act_window',
            'res_model': 'approval.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
            },
        }

    def action_reset_to_draft(self):
        """Mở lại trạng thái chờ nộp để chỉnh sửa hoặc gửi lại."""
        self.check_access('write')
        is_manager = self.env.user.has_group('enterprise_approval.group_approval_manager')
        for rec in self:
            if not is_manager and rec.requester_id.id != self.env.uid:
                raise exceptions.AccessError(rec.env._('Chỉ người tạo hoặc quản trị viên mới có quyền đặt lại yêu cầu về trạng thái nháp.'))

            rec.write({
                'state': 'draft',
                'date_confirmed': False,
                'confirmed_by': False,
                'rejection_reason': False,
            })
            rec.approver_ids.write({'status': 'new'})
            rec._log_history('reset', rec.env._('Đặt về Nháp để chỉnh sửa'))
            rec.message_post(body=rec.env._('Yêu cầu đã được đặt lại về trạng thái <b>Nháp</b>.'))

    def action_cancel(self):
        """Hủy phiếu yêu cầu."""
        self.check_access('write')
        is_manager = self.env.user.has_group('enterprise_approval.group_approval_manager')
        for rec in self:
            if not is_manager and rec.requester_id.id != self.env.uid:
                raise exceptions.AccessError(rec.env._('Chỉ người tạo hoặc quản trị viên mới có thể hủy yêu cầu này.'))

            rec.write({'state': 'cancelled'})
            rec.approver_ids.write({'status': 'cancel'})
            rec._log_history('cancel', rec.env._('Yêu cầu phê duyệt đã bị hủy'))
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            rec.message_post(body=rec.env._('Yêu cầu phê duyệt đã được hủy.'))

    def action_attach_document(self):
        """Mở trình quản lý tệp đính kèm."""
        self.ensure_one()
        return {
            'name': self.env._('Tài liệu đính kèm'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,list,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
            'target': 'current',
        }

    def action_view_attachments(self):
        """Xem danh sách tài liệu đính kèm của phiếu này."""
        self.ensure_one()
        return {
            'name': self.env._('Tài liệu đính kèm'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,list,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _log_history(self, action, comment=False):
        """Tạo bản ghi lịch sử xử lý."""
        for rec in self:
            self.env['approval.history'].create({
                'request_id': rec.id,
                'user_id': self.env.uid,
                'action': action,
                'timestamp': fields.Datetime.now(),
                'comment': comment,
            })

    def _schedule_approver_activity(self):
        """Lên lịch hoạt động nhắc việc (Todo) cho người duyệt."""
        for rec in self:
            if rec.approver_id:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=rec.approver_id.id,
                    summary=rec.env._('Cần phê duyệt: %s', rec.title),
                    note=rec.env._(
                        '<b>%s</b> đã nộp một phiếu yêu cầu phê duyệt: "%s". Vui lòng xem xét và xử lý.',
                        rec.requester_id.name, rec.title
                    ),
                )
