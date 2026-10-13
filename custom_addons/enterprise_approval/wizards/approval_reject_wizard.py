# -*- coding: utf-8 -*-
from odoo import models, fields, exceptions, _

class ApprovalRejectWizard(models.TransientModel):
    """Cửa sổ bật lên để nhập lý do từ chối yêu cầu phê duyệt."""

    _name = 'approval.reject.wizard'
    _description = 'Từ chối yêu cầu phê duyệt'

    request_id = fields.Many2one(
        comodel_name='approval.request',
        string='Yêu cầu phê duyệt',
        required=True,
    )
    reason = fields.Text(
        string='Lý do từ chối',
        required=True,
        help='Vui lòng giải thích rõ ràng lý do không phê duyệt yêu cầu này',
    )

    def action_confirm_reject(self):
        """Xác nhận từ chối và cập nhật trạng thái phiếu yêu cầu."""
        self.ensure_one()
        req = self.request_id

        is_manager = self.env.user.has_group('enterprise_approval.group_approval_manager')
        current_uid = self.env.uid

        if req.state != 'submitted':
            raise exceptions.UserError(self.env._('This request is no longer awaiting approval.'))

        approver_uids = req.approver_ids.mapped('user_id').ids
        if not is_manager and req.approver_id.id != current_uid and current_uid not in approver_uids:
            raise exceptions.AccessError(self.env._('You do not have permission to reject this request.'))

        req.approver_ids.filtered(lambda a: a.user_id.id == current_uid).write({'status': 'refused'})

        req.write({
            'state': 'rejected',
            'date_confirmed': fields.Datetime.now(),
            'confirmed_by': self.env.user.id,
            'rejection_reason': self.reason,
        })

        # Ghi nhật ký lịch sử
        req._log_history('reject', self.env._('Request rejected. Reason: %s', self.reason))

        # Hoàn tất hoạt động nhắc việc
        req.activity_feedback(['mail.mail_activity_data_todo'])

        # Gửi thông báo vào Chatter
        req.message_post(
            body=self.env._(
                '❌ <b>REQUEST REJECTED!</b><br/>'
                'Rejected by: <b>%s</b><br/>'
                'Reason: <i>%s</i>',
                self.env.user.name, self.reason,
            ),
            message_type='notification',
        )

        return {'type': 'ir.actions.act_window_close'}
