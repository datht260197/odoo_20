# -*- coding: utf-8 -*-
"""
IT Helpdesk - Website Portal Controller
Cung cấp giao diện web cho nhân viên gửi và theo dõi phiếu hỗ trợ IT.
"""

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, ValidationError


class ItHelpdeskPortal(CustomerPortal):
    """
    Controller xử lý giao diện Portal cho module IT Helpdesk.
    Kế thừa CustomerPortal để tích hợp liền mạch vào trang /my của Odoo.
    """

    # =========================================================================
    # Portal Home: Hiển thị số lượng ticket trong mục My Documents
    # =========================================================================

    def _prepare_home_portal_values(self, counters):
        """Thêm số lượng phiếu IT của nhân viên vào trang /my/home."""
        values = super()._prepare_home_portal_values(counters)
        if 'it_ticket_count' in counters:
            employee = request.env['hr.employee'].sudo().search(
                [('user_id', '=', request.env.uid)], limit=1
            )
            domain = self._get_ticket_domain(employee)
            values['it_ticket_count'] = (
                request.env['it.ticket'].sudo().search_count(domain)
                if employee else 0
            )
        return values

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_ticket_domain(self, employee=None):
        """Trả về domain lọc ticket theo nhân viên đang đăng nhập."""
        if not employee:
            employee = request.env['hr.employee'].sudo().search(
                [('user_id', '=', request.env.uid)], limit=1
            )
        if employee:
            return [('employee_id', '=', employee.id)]
        # Nếu không tìm thấy hr.employee, lọc theo user
        return [('create_uid', '=', request.env.uid)]

    def _get_state_label(self, state):
        """Trả về nhãn hiển thị cho từng trạng thái phiếu."""
        labels = {
            'new': _('Mới tiếp nhận'),
            'in_progress': _('Đang xử lý'),
            'waiting': _('Đang chờ'),
            'done': _('Hoàn thành'),
            'cancelled': _('Đã hủy'),
        }
        return labels.get(state, state)

    def _get_priority_label(self, priority):
        """Trả về nhãn hiển thị cho mức độ ưu tiên."""
        labels = {
            '0': _('Thấp'),
            '1': _('Bình thường'),
            '2': _('Cao'),
            '3': _('Khẩn cấp'),
        }
        return labels.get(priority, priority)

    # =========================================================================
    # Route: /it/helpdesk — Danh sách phiếu của nhân viên
    # =========================================================================

    @http.route(
        ['/it/helpdesk', '/it/helpdesk/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
        methods=['GET'],
    )
    def portal_it_helpdesk_list(self, page=1, sortby='date', filterby='all', **kw):
        """
        Hiển thị danh sách phiếu hỗ trợ IT của nhân viên đang đăng nhập.
        Hỗ trợ phân trang, sắp xếp và lọc theo trạng thái.
        """
        ITicket = request.env['it.ticket'].sudo()
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1
        )
        base_domain = self._get_ticket_domain(employee)

        # --- Cấu hình sắp xếp ---
        searchbar_sortings = {
            'date': {
                'label': _('Mới nhất'),
                'order': 'date_opened desc',
            },
            'name': {
                'label': _('Mã phiếu'),
                'order': 'name asc',
            },
            'priority': {
                'label': _('Mức độ ưu tiên'),
                'order': 'priority desc',
            },
            'state': {
                'label': _('Trạng thái'),
                'order': 'state asc',
            },
        }
        order = searchbar_sortings.get(sortby, searchbar_sortings['date'])['order']

        # --- Cấu hình lọc ---
        searchbar_filters = {
            'all': {'label': _('Tất cả'), 'domain': []},
            'new': {'label': _('Mới tiếp nhận'), 'domain': [('state', '=', 'new')]},
            'in_progress': {'label': _('Đang xử lý'), 'domain': [('state', '=', 'in_progress')]},
            'waiting': {'label': _('Đang chờ'), 'domain': [('state', '=', 'waiting')]},
            'done': {'label': _('Hoàn thành'), 'domain': [('state', '=', 'done')]},
        }
        filter_domain = searchbar_filters.get(filterby, searchbar_filters['all'])['domain']
        domain = base_domain + filter_domain

        # --- Phân trang ---
        step = 10
        total = ITicket.search_count(domain)
        pager = portal_pager(
            url='/it/helpdesk',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=total,
            page=page,
            step=step,
        )

        tickets = ITicket.search(domain, order=order, limit=step, offset=pager['offset'])

        values = {
            'page_name': 'it_helpdesk',
            'tickets': tickets,
            'pager': pager,
            'sortby': sortby,
            'filterby': filterby,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'default_url': '/it/helpdesk',
            'employee': employee,
            'get_state_label': self._get_state_label,
            'get_priority_label': self._get_priority_label,
        }
        return request.render('it_helpdesk.portal_it_helpdesk_list', values)

    # =========================================================================
    # Route: /it/helpdesk/<id> — Chi tiết phiếu
    # =========================================================================

    @http.route(
        ['/it/helpdesk/<int:ticket_id>'],
        type='http',
        auth='user',
        website=True,
        methods=['GET'],
    )
    def portal_it_helpdesk_detail(self, ticket_id, **kw):
        """Hiển thị chi tiết một phiếu hỗ trợ IT."""
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1
        )
        domain = self._get_ticket_domain(employee) + [('id', '=', ticket_id)]
        ticket = request.env['it.ticket'].sudo().search(domain, limit=1)

        if not ticket:
            return request.redirect('/it/helpdesk')

        values = {
            'page_name': 'it_helpdesk_detail',
            'ticket': ticket,
            'employee': employee,
            'get_state_label': self._get_state_label,
            'get_priority_label': self._get_priority_label,
        }
        return request.render('it_helpdesk.portal_it_helpdesk_detail', values)

    # =========================================================================
    # Route: /it/helpdesk/new — Form gửi yêu cầu mới
    # =========================================================================

    @http.route(
        ['/it/helpdesk/new'],
        type='http',
        auth='user',
        website=True,
        methods=['GET', 'POST'],
    )
    def portal_it_helpdesk_new(self, **post):
        """
        GET  → Hiển thị form gửi yêu cầu mới.
        POST → Xử lý dữ liệu form, tạo ticket và redirect về danh sách.
        """
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1
        )
        templates = request.env['it.ticket.template'].sudo().search(
            [('active', '=', True)],
            order='name asc',
        )

        # ---- Xử lý POST (submit form) ----
        if request.httprequest.method == 'POST':
            errors = {}
            title = post.get('title', '').strip()
            description = post.get('description', '').strip()
            template_id = post.get('template_id', '')
            priority = post.get('priority', '1')

            # Validation
            if not title:
                errors['title'] = _('Vui lòng nhập tiêu đề yêu cầu.')

            if not errors:
                vals = {
                    'title': title,
                    'description': description or False,
                    'priority': priority,
                    'employee_id': employee.id if employee else False,
                    'state': 'new',
                }
                if template_id and template_id.isdigit():
                    vals['template_id'] = int(template_id)

                new_ticket = request.env['it.ticket'].sudo().create(vals)
                # Gửi thông báo chatter tự động
                new_ticket.sudo().message_post(
                    body=_(
                        'Phiếu hỗ trợ được tạo bởi <b>%s</b> qua cổng thông tin nhân viên.'
                    ) % request.env.user.name,
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                return request.redirect('/it/helpdesk?success=1')

            # Nếu có lỗi → hiển thị lại form với dữ liệu đã nhập
            values = {
                'page_name': 'it_helpdesk_new',
                'templates': templates,
                'employee': employee,
                'errors': errors,
                'post': post,
                'priority_options': [
                    ('0', _('Thấp')),
                    ('1', _('Bình thường')),
                    ('2', _('Cao')),
                    ('3', _('Khẩn cấp')),
                ],
            }
            return request.render('it_helpdesk.portal_it_helpdesk_new', values)

        # ---- Hiển thị form trống (GET) ----
        # Nếu có template_id trong query string → tự động chọn sẵn
        preselect_template = None
        tpl_id = request.httprequest.args.get('template_id', '')
        if tpl_id and tpl_id.isdigit():
            preselect_template = request.env['it.ticket.template'].sudo().browse(int(tpl_id))
            if not preselect_template.exists():
                preselect_template = None

        success = request.httprequest.args.get('success', '')

        values = {
            'page_name': 'it_helpdesk_new',
            'templates': templates,
            'employee': employee,
            'errors': {},
            'post': {},
            'preselect_template': preselect_template,
            'priority_options': [
                ('0', _('Thấp')),
                ('1', _('Bình thường')),
                ('2', _('Cao')),
                ('3', _('Khẩn cấp')),
            ],
        }
        return request.render('it_helpdesk.portal_it_helpdesk_new', values)
