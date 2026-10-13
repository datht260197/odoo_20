# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ItTeam(models.Model):
    """Model quản lý đội ngũ hỗ trợ kỹ thuật (Helpdesk Team)."""

    _name = 'it.team'
    _description = 'Helpdesk Team'
    _order = 'sequence, name'

    name = fields.Char(
        string='Tên đội ngũ',
        required=True,
        translate=True,
        help='Tên nhóm hỗ trợ (Ví dụ: Customer Care, IT Support, Phần cứng...)',
    )
    sequence = fields.Integer(
        string='Thứ tự hiển thị',
        default=10,
    )
    active = fields.Boolean(
        string='Đang hoạt động',
        default=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Trưởng nhóm',
        help='Người phụ trách chính của đội ngũ hỗ trợ',
    )
    member_ids = fields.Many2many(
        comodel_name='res.users',
        relation='it_team_res_users_rel',
        column1='team_id',
        column2='user_id',
        string='Thành viên',
        help='Các nhân viên thuộc đội ngũ này',
    )
    color = fields.Integer(
        string='Màu sắc',
        default=0,
    )
    ticket_ids = fields.One2many(
        comodel_name='it.ticket',
        inverse_name='team_id',
        string='Phiếu hỗ trợ',
    )
    ticket_count = fields.Integer(
        string='Tổng số phiếu',
        compute='_compute_ticket_count',
    )
    ticket_open_count = fields.Integer(
        string='Phiếu đang mở',
        compute='_compute_ticket_count',
    )
    ticket_urgent_count = fields.Integer(
        string='Phiếu khẩn cấp',
        compute='_compute_ticket_count',
    )

    def _compute_ticket_count(self):
        """Tính toán số lượng phiếu theo trạng thái cho từng đội."""
        for team in self:
            tickets = team.ticket_ids
            team.ticket_count = len(tickets)
            team.ticket_open_count = len(tickets.filtered(lambda t: t.state in ['new', 'in_progress', 'waiting']))
            team.ticket_urgent_count = len(tickets.filtered(lambda t: t.priority == '3' and t.state not in ['done', 'cancelled']))

    def action_view_tickets(self):
        """Mở danh sách toàn bộ phiếu thuộc đội này."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu hỗ trợ - %s') % self.name,
            'res_model': 'it.ticket',
            'view_mode': 'kanban,list,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id},
        }

    def action_view_open_tickets(self):
        """Mở các phiếu đang mở cần xử lý của đội."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu đang mở - %s') % self.name,
            'res_model': 'it.ticket',
            'view_mode': 'kanban,list,form',
            'domain': [('team_id', '=', self.id), ('state', 'in', ['new', 'in_progress', 'waiting'])],
            'context': {'default_team_id': self.id},
        }
