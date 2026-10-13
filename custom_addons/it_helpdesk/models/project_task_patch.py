# -*- coding: utf-8 -*-
"""
Mở rộng model project.task từ module it_helpdesk.

Mục tiêu:
    1. Chặn nhân viên thường chuyển task sang stage đã đóng (fold=True).
    2. Bảo vệ nội dung cốt lõi của task khi đã vào xử lý/hoàn thành.
    3. Kiểm soát quyền sửa đổi — chỉ người được gán (user_id) hoặc
       người tạo (create_uid) mới được sửa task không thuộc của mình.

Quy tắc nhóm quyền áp dụng:
    - ``it_helpdesk.group_it_manager`` : Toàn quyền (bypass mọi ràng buộc)
    - ``project.group_project_manager`` : Project Manager cũng bypass
    - Người dùng thông thường: chịu tất cả ràng buộc bên dưới
"""
import logging

from odoo import api, exceptions, fields, models, _

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------------

# Trường cốt lõi của task — không được sửa khi task đã vào stage đóng
# hoặc khi người dùng không phải người được gán / người tạo
_TASK_PROTECTED_FIELDS = frozenset([
    'name',           # Tiêu đề task
    'description',    # Nội dung mô tả
    'planned_hours',  # Số giờ dự kiến
    'date_deadline',  # Deadline
    'project_id',     # Dự án thuộc về
])


class ProjectTaskPatch(models.Model):
    """Kế thừa project.task để tích hợp kiểm soát quyền của IT Helpdesk.

    Áp dụng hai lớp bảo vệ qua ghi đè ``write()``:

    Lớp 1 — Chặn chuyển stage "đóng" (fold=True):
        Nhân viên thường không thể kéo task sang cột Done/Hoàn thành
        trên Kanban nếu không thuộc nhóm quản lý.

    Lớp 2 — Bảo vệ nội dung cốt lõi:
        Khi task đã vào stage đóng, chỉ người được gán (user_id),
        người tạo (create_uid) hoặc nhóm quản lý mới được sửa
        các trường cốt lõi.
    """

    _inherit = 'project.task'

    # =========================================================================
    # Helper: kiểm tra nhóm quyền
    # =========================================================================

    def _task_is_it_manager(self):
        """Trả về True nếu user hiện tại là IT Manager (it_helpdesk)."""
        return self.env.user.has_group('it_helpdesk.group_it_manager')

    def _task_is_project_manager(self):
        """Trả về True nếu user hiện tại là Project Manager (module project)."""
        return self.env.user.has_group('project.group_project_manager')

    def _task_has_elevated_rights(self):
        """Trả về True nếu user có quyền quản lý (IT Manager hoặc Project Manager)."""
        return (
            self.env.su
            or self._task_is_it_manager()
            or self._task_is_project_manager()
        )

    def _task_user_is_assigned_or_creator(self, task):
        """Kiểm tra user hiện tại có phải người được gán hoặc người tạo task không.

        Xét cả trường hợp Odoo 18 Community (user_id) lẫn
        Odoo 17+ Enterprise (user_ids Many2many).
        """
        uid = self.env.uid

        # Trường hợp Many2many user_ids (Odoo 17+ Enterprise / some community)
        if hasattr(task, 'user_ids') and task.user_ids:
            is_assigned = uid in task.user_ids.ids
        else:
            # Many2one user_id (Odoo Community standard)
            is_assigned = (task.user_id.id == uid) if task.user_id else False

        is_creator = (task.create_uid.id == uid) if task.create_uid else False
        return is_assigned or is_creator

    # =========================================================================
    # ORM Override: write()
    # =========================================================================

    def write(self, vals):
        """Ghi đè write() để áp dụng 2 lớp bảo vệ nghiệp vụ.

        **Lớp 1 — Chặn chuyển sang stage đóng (fold=True):**
            Nếu vals chứa ``stage_id`` trỏ đến stage có ``fold=True``
            và user hiện tại KHÔNG có quyền quản lý → raise UserError.

        **Lớp 2 — Bảo vệ trường cốt lõi khi task đã đóng:**
            Nếu task đang ở stage đóng VÀ user không phải người gán/tạo
            VÀ không có quyền quản lý → chặn sửa các trường _TASK_PROTECTED_FIELDS.
        """
        # Superuser luôn bypass
        if self.env.su:
            return super().write(vals)

        has_elevated = self._task_has_elevated_rights()

        # ==================================================================
        # LỚP 1: Kiểm soát chuyển sang stage đóng (fold=True)
        # ==================================================================
        new_stage_id = vals.get('stage_id')
        if new_stage_id and not has_elevated:
            new_stage = self.env['project.task.type'].browse(new_stage_id)
            if new_stage.exists() and new_stage.fold:
                raise exceptions.UserError(_(
                    'Bạn không có quyền chuyển công việc sang cột "%(stage)s" '
                    '(trạng thái Hoàn thành / Đóng).\n\n'
                    'Chỉ Quản lý IT hoặc Quản lý Dự án mới được thực hiện '
                    'thao tác này. Vui lòng liên hệ người quản lý của bạn.',
                    stage=new_stage.name,
                ))

        # ==================================================================
        # LỚP 2: Bảo vệ trường cốt lõi khi task đang ở stage đóng
        # ==================================================================
        if not has_elevated:
            protected_attempted = _TASK_PROTECTED_FIELDS & set(vals.keys())
            if protected_attempted:
                for task in self:
                    # Chỉ kiểm tra nếu task đang ở stage đóng
                    if not task.stage_id or not task.stage_id.fold:
                        continue

                    # Kiểm tra user có phải người được gán / tạo không
                    if not self._task_user_is_assigned_or_creator(task):
                        field_labels = []
                        for f in protected_attempted:
                            field_def = task._fields.get(f)
                            if field_def:
                                field_labels.append(
                                    field_def.string or f
                                )
                        raise exceptions.UserError(_(
                            'Bạn không được phép chỉnh sửa các trường: %(fields)s\n\n'
                            'Công việc "%(task)s" đang ở trạng thái Hoàn thành/Đóng. '
                            'Chỉ người được gán trực tiếp, người tạo hoặc quản lý '
                            'mới có thể thay đổi nội dung này.',
                            fields=', '.join(field_labels),
                            task=task.name,
                        ))

        return super().write(vals)

    # =========================================================================
    # @api.constrains — Tầng ràng buộc DB bổ sung
    # =========================================================================

    @api.constrains('stage_id')
    def _check_stage_transition_permission(self):
        """Ràng buộc DB: Xác thực quyền chuyển stage đóng.

        Đây là tầng bảo vệ thứ 2 (backup) sau write().
        Đảm bảo ngay cả khi bypass write() cũng bị chặn ở tầng constraints.

        Lưu ý: constrains chạy SAU khi ghi, nên đây chỉ là lưới an toàn;
        write() vẫn là kiểm soát chính.
        """
        # Bỏ qua nếu superuser hoặc có quyền cao
        if self.env.su or self._task_has_elevated_rights():
            return

        for task in self:
            if task.stage_id and task.stage_id.fold:
                raise exceptions.ValidationError(_(
                    'Công việc "%(task)s" không thể chuyển sang stage '
                    '"%(stage)s" (Hoàn thành/Đóng).\n\n'
                    'Bạn không có quyền thực hiện thao tác này. '
                    'Vui lòng liên hệ Quản lý IT hoặc Quản lý Dự án.',
                    task=task.name,
                    stage=task.stage_id.name,
                ))
