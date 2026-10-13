# -*- coding: utf-8 -*-
# Part of Custom Addons. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ItDepartmentRoleTemplate(models.Model):
    """
    Model cấu hình mẫu vai trò và nhóm quyền hạn theo vị trí / phòng ban.
    Thiết kế độc lập (Self-contained) sử dụng bảng trung gian riêng,
    TUYỆT ĐỐI KHÔNG thêm cột mới vào các bảng cốt lõi (res_users, hr_employee, hr_department)
    để đảm bảo giữ nguyên cấu trúc database hiện tại và không gây lỗi UndefinedColumn.
    """
    _name = 'it.department.role.template'
    _description = 'Mẫu vai trò và phân quyền theo phòng ban'
    _order = 'sequence, name'

    name = fields.Char(
        string='Tên vai trò / Mẫu quyền',
        required=True,
        help='Ví dụ: Trưởng phòng IT, Nhân viên IT, Trưởng phòng Kinh doanh, Nhân viên Kinh doanh',
    )
    code = fields.Char(
        string='Mã vai trò',
        help='Mã định danh nội bộ, ví dụ: IT_MGR, IT_USER, SALE_MGR',
    )
    sequence = fields.Integer(
        string='Thứ tự',
        default=10,
    )
    active = fields.Boolean(
        string='Hoạt động',
        default=True,
    )
    department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Phòng ban áp dụng',
        ondelete='set null',
        help='Phòng ban gắn với vai trò này (để trống nếu áp dụng chung toàn công ty).',
    )
    role_type = fields.Selection(
        selection=[
            ('manager', 'Trưởng phòng / Quản lý'),
            ('employee', 'Nhân viên / Thành viên'),
            ('other', 'Khác'),
        ],
        string='Cấp bậc vai trò',
        default='employee',
        required=True,
        help='Phân loại cấp bậc để hệ thống tự động nhận diện khi phân bổ nhân sự.',
    )
    group_ids = fields.Many2many(
        comodel_name='res.groups',
        relation='it_role_template_res_groups_rel',
        column1='template_id',
        column2='group_id',
        string='Nhóm quyền Odoo (Groups)',
        help='Tất cả các nhóm quyền này sẽ được tự động gán cho tài khoản người dùng.',
    )
    description = fields.Text(
        string='Mô tả quyền hạn & nhiệm vụ',
        help='Ghi chú tóm tắt quyền hạn: Xem báo cáo, duyệt phiếu, quản lý task...',
    )
    user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='it_role_template_users_rel',
        column1='template_id',
        column2='user_id',
        string='Tài khoản người dùng áp dụng',
        help='Danh sách tài khoản được gán vai trò này. Lưu ở bảng trung gian riêng, không sửa bảng res_users.',
    )
    employee_ids = fields.Many2many(
        comodel_name='hr.employee',
        relation='it_role_template_employees_rel',
        column1='template_id',
        column2='employee_id',
        string='Nhân viên áp dụng',
        help='Danh sách nhân viên được gán vai trò này. Lưu ở bảng trung gian riêng, không sửa bảng hr_employee.',
    )
    user_count = fields.Integer(
        string='Số người dùng',
        compute='_compute_user_count',
        store=False,
    )

    @api.depends('user_ids', 'employee_ids.user_id')
    def _compute_user_count(self):
        for template in self:
            all_users = template.user_ids | template.employee_ids.mapped('user_id')
            template.user_count = len(all_users)

    def apply_to_user(self, user):
        """
        Gán toàn bộ danh sách group_ids trong template vào user.groups_id.
        Sử dụng command (4, id) để thêm quyền mà không làm mất các quyền đặc thù đã có.
        """
        self.ensure_one()
        if not user or not self.group_ids:
            return False

        commands = [(4, group.id) for group in self.group_ids]
        user.sudo().write({'group_ids': commands})
        _logger.info(
            "Đã tự động gán %d nhóm quyền từ template '%s' cho tài khoản '%s' (ID: %s)",
            len(self.group_ids), self.name, user.name, user.id
        )
        return True

    def action_load_department_members(self):
        """
        Quét và tự động nạp nhân sự thuộc phòng ban vào vai trò này:
        - Nếu role_type là 'manager': Nạp Trưởng phòng.
        - Nếu role_type là 'employee': Nạp toàn bộ nhân viên thuộc phòng ban.
        """
        self.ensure_one()
        if not self.department_id:
            raise UserError(_("Vui lòng chọn 'Phòng ban áp dụng' trước khi quét nhân sự."))

        if self.role_type == 'manager':
            manager = self.department_id.manager_id
            if not manager:
                raise UserError(_("Phòng ban '%s' hiện chưa có Trưởng phòng được chỉ định.") % self.department_id.name)
            self.employee_ids = [(4, manager.id)]
            if manager.user_id:
                self.user_ids = [(4, manager.user_id.id)]
        else:
            members = self.department_id.member_ids
            if not members:
                raise UserError(_("Phòng ban '%s' hiện chưa có nhân viên nào.") % self.department_id.name)
            self.employee_ids = [(4, m.id) for m in members]
            users = members.mapped('user_id')
            if users:
                self.user_ids = [(4, u.id) for u in users]

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã nạp nhân sự phòng ban'),
                'message': _('Đã nạp danh sách nhân sự từ phòng ban "%s" vào vai trò "%s". Bấm "Đồng bộ quyền" để cấp quyền.') % (
                    self.department_id.name, self.name
                ),
                'sticky': False,
                'type': 'success',
            }
        }

    def action_apply_to_users(self):
        """
        Nút bấm thủ công cho phép Admin đồng bộ tức thì các nhóm quyền
        cho toàn bộ người dùng và nhân viên đang liên kết với vai trò này.
        """
        self.ensure_one()
        target_users = self.user_ids | self.employee_ids.mapped('user_id')
        if not target_users:
            raise UserError(_("Chưa có người dùng hoặc nhân viên nào trong danh sách vai trò '%s'.") % self.name)

        count = 0
        for user in target_users:
            if self.apply_to_user(user):
                count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đồng bộ quyền thành công'),
                'message': _('Đã cập nhật %d nhóm quyền cho %d tài khoản người dùng thuộc vai trò "%s".') % (
                    len(self.group_ids), count, self.name
                ),
                'sticky': False,
                'type': 'success',
            }
        }


class HrEmployee(models.Model):
    """
    Tự động hóa gắn quyền khi nhân viên được xếp vào phòng ban:
    Tận dụng quan hệ trung gian của it.department.role.template,
    TUYỆT ĐỐI KHÔNG thêm cột mới vào bảng hr_employee.
    """
    _inherit = 'hr.employee'

    @api.model_create_multi
    def create(self, vals_list):
        employees = super(HrEmployee, self).create(vals_list)
        for emp in employees:
            emp._auto_sync_role_from_department()
        return employees

    def write(self, vals):
        res = super(HrEmployee, self).write(vals)
        if 'department_id' in vals or 'user_id' in vals:
            for emp in self:
                emp._auto_sync_role_from_department()
        return res

    def _auto_sync_role_from_department(self):
        """Tìm mẫu vai trò tương ứng của phòng ban và tự động gán quyền."""
        for emp in self:
            if not emp.department_id or not emp.user_id:
                continue

            # Xác định cấp bậc: Trưởng phòng hay Nhân viên
            is_manager = bool(emp.department_id.manager_id and emp.id == emp.department_id.manager_id.id)
            target_role_type = 'manager' if is_manager else 'employee'

            # Tìm template thuộc phòng ban này khớp cấp bậc
            template = self.env['it.department.role.template'].sudo().search([
                ('department_id', '=', emp.department_id.id),
                ('role_type', '=', target_role_type),
                ('active', '=', True),
            ], limit=1)

            if template:
                template.sudo().write({
                    'employee_ids': [(4, emp.id)],
                    'user_ids': [(4, emp.user_id.id)],
                })
                template.apply_to_user(emp.user_id)
