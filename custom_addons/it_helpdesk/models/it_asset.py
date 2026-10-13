# -*- coding: utf-8 -*-
from odoo import models, fields


class ItAsset(models.Model):
    """Model quản lý tài sản CNTT của doanh nghiệp."""

    _name = 'it.asset'
    _description = 'IT Asset'
    _order = 'name asc'
    _rec_name = 'name'

    # -------------------------------------------------------------------------
    # Thông tin thiết bị
    # -------------------------------------------------------------------------
    name = fields.Char(
        string='Tên thiết bị / Mã tài sản',
        required=True,
        help='Tên hoặc mã định danh của thiết bị CNTT',
    )
    serial_number = fields.Char(
        string='Số Serial / Service Tag',
        copy=False,
        help='Số serial hoặc service tag ghi trên thiết bị',
    )
    category_type = fields.Selection(
        selection=[
            ('laptop', 'Laptop'),
            ('desktop', 'Máy bàn'),
            ('monitor', 'Màn hình'),
            ('printer', 'Máy in'),
            ('network', 'Thiết bị mạng'),
            ('other', 'Khác'),
        ],
        string='Loại thiết bị',
        required=True,
        default='laptop',
        help='Phân loại loại thiết bị CNTT',
    )

    # -------------------------------------------------------------------------
    # Thông tin cấp phát
    # -------------------------------------------------------------------------
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Nhân viên sử dụng',
        help='Nhân viên đang được cấp phát và sử dụng thiết bị này',
    )
    date_assigned = fields.Date(
        string='Ngày cấp phát',
        help='Ngày bàn giao thiết bị cho nhân viên',
    )

    # -------------------------------------------------------------------------
    # Trạng thái thiết bị
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection=[
            ('in_use', 'Đang sử dụng'),
            ('in_stock', 'Trong kho'),
            ('repairing', 'Đang sửa chữa'),
            ('disposed', 'Đã thanh lý'),
        ],
        string='Trạng thái',
        default='in_stock',
        required=True,
        help='Trạng thái hiện tại của tài sản CNTT',
    )

    # -------------------------------------------------------------------------
    # Thông tin kỹ thuật bổ sung
    # -------------------------------------------------------------------------
    brand = fields.Char(
        string='Thương hiệu',
        help='Hãng sản xuất (Dell, HP, Lenovo, ...)',
    )
    model_name = fields.Char(
        string='Model',
        help='Tên model cụ thể của thiết bị',
    )
    purchase_date = fields.Date(
        string='Ngày mua',
        help='Ngày doanh nghiệp mua thiết bị',
    )
    warranty_expiry = fields.Date(
        string='Hết hạn bảo hành',
        help='Ngày hết hạn bảo hành của thiết bị',
    )
    notes = fields.Text(
        string='Ghi chú',
        help='Ghi chú thêm về tình trạng hoặc cấu hình thiết bị',
    )
    color = fields.Integer(
        string='Màu Kanban',
        default=0,
    )

    # =========================================================================
    # Computed / Smart Buttons
    # =========================================================================
    ticket_ids = fields.One2many(
        comodel_name='it.ticket',
        inverse_name='asset_id',
        string='Phiếu hỗ trợ liên quan',
    )
    ticket_count = fields.Integer(
        string='Số phiếu hỗ trợ',
        compute='_compute_ticket_count',
    )

    def _compute_ticket_count(self):
        """Đếm số phiếu hỗ trợ liên kết với tài sản này."""
        for record in self:
            record.ticket_count = len(record.ticket_ids)

    # =========================================================================
    # Action methods
    # =========================================================================

    def action_set_in_use(self):
        self.write({'state': 'in_use'})

    def action_set_in_stock(self):
        self.write({'state': 'in_stock', 'employee_id': False, 'date_assigned': False})

    def action_set_repairing(self):
        self.write({'state': 'repairing'})

    def action_set_disposed(self):
        self.write({'state': 'disposed'})

    def action_view_tickets(self):
        """Mở danh sách phiếu hỗ trợ liên quan đến tài sản này."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Phiếu hỗ trợ - {self.name}',
            'res_model': 'it.ticket',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
        }
