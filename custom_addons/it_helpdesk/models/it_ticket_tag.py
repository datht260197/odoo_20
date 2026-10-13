# -*- coding: utf-8 -*-
from odoo import models, fields


class ItTicketTag(models.Model):
    """Model quản lý thẻ phân loại phiếu hỗ trợ (Ticket Tags)."""

    _name = 'it.ticket.tag'
    _description = 'Ticket Tag'
    _order = 'name'

    name = fields.Char(
        string='Tên thẻ',
        required=True,
        translate=True,
    )
    color = fields.Integer(
        string='Màu sắc',
        default=0,
    )
    active = fields.Boolean(
        string='Đang dùng',
        default=True,
    )
