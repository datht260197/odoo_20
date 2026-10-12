from odoo import fields, models


class TestItem(models.Model):
    _name = 'test.item'
    _description = 'Mục kiểm thử mẫu'

    name = fields.Char(string='Tiêu đề / Tên', required=True)
    description = fields.Text(string='Mô tả chi tiết')
    state = fields.Selection(
        [
            ('draft', 'Nháp'),
            ('confirmed', 'Đã xác nhận'),
            ('done', 'Hoàn thành'),
        ],
        string='Trạng thái',
        default='draft',
        required=True,
    )

    def action_confirm(self):
        self.state = 'confirmed'

    def action_done(self):
        self.state = 'done'
