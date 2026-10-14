from datetime import datetime, timedelta
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFleetDispatch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company_2 = cls.env['res.company'].create({'name': 'Second Fleet Company'})

        # Security Groups
        cls.group_user = cls.env.ref('frontdesk_admin.group_frontdesk_user')
        cls.group_officer = cls.env.ref('frontdesk_admin.group_frontdesk_officer')
        cls.group_manager = cls.env.ref('frontdesk_admin.group_frontdesk_manager')

        # Department Manager
        cls.user_dept_manager = cls.env['res.users'].create({
            'name': 'Dept Manager Minh',
            'login': 'dept_manager_minh',
            'email': 'minh@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.employee_dept_manager = cls.env['hr.employee'].create({
            'name': 'Dept Manager Minh',
            'user_id': cls.user_dept_manager.id,
            'company_id': cls.company.id,
        })

        # Subordinate Requester Employee
        cls.user_requester = cls.env['res.users'].create({
            'name': 'Employee Nam',
            'login': 'employee_nam',
            'email': 'nam@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.employee_requester = cls.env['hr.employee'].create({
            'name': 'Employee Nam',
            'user_id': cls.user_requester.id,
            'parent_id': cls.employee_dept_manager.id,
            'company_id': cls.company.id,
        })

        # Other User / Employee (Not in direct reporting line)
        cls.user_other = cls.env['res.users'].create({
            'name': 'Other Employee Lan',
            'login': 'employee_lan',
            'email': 'lan@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.employee_other = cls.env['hr.employee'].create({
            'name': 'Other Employee Lan',
            'user_id': cls.user_other.id,
            'company_id': cls.company.id,
        })

        # Frontdesk Officer
        cls.user_officer = cls.env['res.users'].create({
            'name': 'Officer Thao',
            'login': 'officer_thao',
            'email': 'thao@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_officer.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

        # Frontdesk Manager
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Boss Hung',
            'login': 'boss_hung',
            'email': 'hung@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_manager.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

        # Driver Partner
        cls.driver_partner = cls.env['res.partner'].create({
            'name': 'Driver Tuan',
            'company_id': cls.company.id,
        })

        # Vehicles
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Toyota'})
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Camry 2.5Q',
            'brand_id': cls.brand.id,
        })
        cls.vehicle_1 = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': '29A-12345',
            'odometer': 10000.0,
            'company_id': cls.company.id,
        })
        cls.vehicle_2 = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': '30E-67890',
            'odometer': 5000.0,
            'company_id': cls.company.id,
        })

    def test_01_sequence_generation(self):
        """Verify automatic sequence generation follows DX/%(range_year)s/0001 pattern."""
        now = fields.Datetime.now()
        req = self.env['fleet.dispatch.request'].with_user(self.user_requester).create({
            'employee_id': self.employee_requester.id,
            'destination': 'Hanoi Noi Bai Airport',
            'purpose': 'Welcoming international delegation',
            'passenger_count': 3,
            'start_datetime': now + timedelta(days=1),
            'end_datetime': now + timedelta(days=1, hours=4),
        })
        current_year = fields.Date.today().strftime('%Y')
        self.assertTrue(req.name.startswith(f'DX/{current_year}/'), f"Expected DX/{current_year}/ prefix, got {req.name}")
        self.assertEqual(len(req.name.split('/')[-1]), 4, "Expected 4-digit sequence padding")

    def test_02_full_workflow_happy_path(self):
        """Test full 2-step approval workflow: draft -> to_approve -> approved -> dispatched -> done."""
        now = fields.Datetime.now()
        start_time = now + timedelta(days=2)
        end_time = now + timedelta(days=2, hours=5)

        # 1. Draft creation by Requester
        req = self.env['fleet.dispatch.request'].with_user(self.user_requester).create({
            'employee_id': self.employee_requester.id,
            'destination': 'Hai Phong Port',
            'purpose': 'Site inspection',
            'passenger_count': 2,
            'start_datetime': start_time,
            'end_datetime': end_time,
        })
        self.assertEqual(req.state, 'draft')

        # 2. Submit for approval
        req.with_user(self.user_requester).action_submit()
        self.assertEqual(req.state, 'to_approve')

        # 3. Approved by Department Manager
        req.with_user(self.user_dept_manager).action_approve()
        self.assertEqual(req.state, 'approved')

        # 4. Frontdesk Officer assigns vehicle and driver, then dispatches
        req.with_user(self.user_officer).write({
            'vehicle_id': self.vehicle_1.id,
            'driver_id': self.driver_partner.id,
        })
        req.with_user(self.user_officer).action_dispatch()
        self.assertEqual(req.state, 'dispatched')
        # Check start odometer auto-fetched from vehicle
        self.assertEqual(req.odometer_start, 10000.0)
        # Check calendar event created
        self.assertTrue(req.calendar_event_id, "Linked calendar event must be created")
        self.assertIn(self.vehicle_1.name, req.calendar_event_id.name)
        self.assertIn('Hai Phong Port', req.calendar_event_id.name)

        # 5. Trip return: Record end odometer and complete
        req.with_user(self.user_officer).write({'odometer_end': 10250.0})
        req.with_user(self.user_officer).action_done()
        self.assertEqual(req.state, 'done')

        # Check native fleet.vehicle.odometer record created
        latest_odometer = self.env['fleet.vehicle.odometer'].search([
            ('vehicle_id', '=', self.vehicle_1.id),
        ], order='id desc', limit=1)
        self.assertTrue(latest_odometer, "Native fleet odometer record must be created")
        self.assertEqual(latest_odometer.value, 10250.0)

    def test_03_approval_security_checks(self):
        """Verify unauthorized users cannot approve/reject requests."""
        now = fields.Datetime.now()
        req = self.env['fleet.dispatch.request'].with_user(self.user_requester).create({
            'employee_id': self.employee_requester.id,
            'destination': 'Bac Ninh Industrial Zone',
            'purpose': 'Factory visit',
            'passenger_count': 1,
            'start_datetime': now + timedelta(days=3),
            'end_datetime': now + timedelta(days=3, hours=3),
        })
        req.with_user(self.user_requester).action_submit()

        # Other unrelated user tries to approve -> AccessError
        with self.assertRaises(AccessError):
            req.with_user(self.user_other).action_approve()

        # Other unrelated user tries to reject -> AccessError
        with self.assertRaises(AccessError):
            req.with_user(self.user_other).action_reject()

        # Frontdesk Manager CAN approve even if not direct manager
        req.with_user(self.user_manager).action_approve()
        self.assertEqual(req.state, 'approved')

    def test_04_odometer_validation(self):
        """Verify odometer constraints: end >= start and end odometer required on done."""
        now = fields.Datetime.now()
        req = self.env['fleet.dispatch.request'].create({
            'employee_id': self.employee_requester.id,
            'destination': 'Ninh Binh',
            'purpose': 'Branch audit',
            'start_datetime': now + timedelta(days=4),
            'end_datetime': now + timedelta(days=4, hours=6),
            'vehicle_id': self.vehicle_1.id,
            'driver_id': self.driver_partner.id,
            'state': 'dispatched',
            'odometer_start': 10000.0,
        })

        # Missing odometer_end when marking done -> UserError
        with self.assertRaises(UserError):
            req.action_done()

        # End odometer less than start odometer -> ValidationError
        with self.assertRaises(ValidationError):
            req.write({'odometer_end': 9800.0})

    def test_05_anti_collision_constraint(self):
        """Verify collision prevention: overlapping trips on same vehicle in approved/dispatched rejected."""
        base_time = fields.Datetime.now() + timedelta(days=5)
        # Booking 1: 08:00 -> 12:00
        trip_1 = self.env['fleet.dispatch.request'].create({
            'employee_id': self.employee_requester.id,
            'destination': 'Location A',
            'purpose': 'Meeting A',
            'start_datetime': base_time + timedelta(hours=8),
            'end_datetime': base_time + timedelta(hours=12),
            'vehicle_id': self.vehicle_1.id,
            'driver_id': self.driver_partner.id,
            'state': 'approved',
        })

        # Booking 2 overlapping: 10:00 -> 14:00 on SAME vehicle
        trip_2 = self.env['fleet.dispatch.request'].create({
            'employee_id': self.employee_other.id,
            'destination': 'Location B',
            'purpose': 'Meeting B',
            'start_datetime': base_time + timedelta(hours=10),
            'end_datetime': base_time + timedelta(hours=14),
            'vehicle_id': self.vehicle_1.id,
            'driver_id': self.driver_partner.id,
            'state': 'draft',
        })

        # When moving trip_2 to approved, should raise collision ValidationError
        with self.assertRaises(ValidationError):
            trip_2.write({'state': 'approved'})

        # Different vehicle should approve without issue
        trip_2.write({'vehicle_id': self.vehicle_2.id})
        trip_2.write({'state': 'approved'})
        self.assertEqual(trip_2.state, 'approved')

        # Non-overlapping time on vehicle_1 (13:00 -> 16:00) should approve cleanly
        trip_3 = self.env['fleet.dispatch.request'].create({
            'employee_id': self.employee_requester.id,
            'destination': 'Location C',
            'purpose': 'Meeting C',
            'start_datetime': base_time + timedelta(hours=13),
            'end_datetime': base_time + timedelta(hours=16),
            'vehicle_id': self.vehicle_1.id,
            'driver_id': self.driver_partner.id,
            'state': 'approved',
        })
        self.assertEqual(trip_3.state, 'approved')

    def test_06_calendar_sync_and_cancellation(self):
        """Verify calendar event synchronization on datetime change and deletion on cancel."""
        base_time = fields.Datetime.now() + timedelta(days=6)
        req = self.env['fleet.dispatch.request'].create({
            'employee_id': self.employee_requester.id,
            'destination': 'Conference Hall',
            'purpose': 'Annual Summit',
            'start_datetime': base_time,
            'end_datetime': base_time + timedelta(hours=3),
            'vehicle_id': self.vehicle_1.id,
            'driver_id': self.driver_partner.id,
            'state': 'approved',
        })
        req.action_dispatch()
        event = req.calendar_event_id
        self.assertTrue(event.exists())

        # Update end datetime
        new_end = base_time + timedelta(hours=6)
        req.write({'end_datetime': new_end})
        self.assertEqual(event.stop, new_end, "Calendar event stop time must synchronize")

        # Cancel request -> event unlinked
        event_id = event.id
        req.action_cancel()
        self.assertEqual(req.state, 'cancelled')
        self.assertFalse(req.calendar_event_id)
        self.assertFalse(self.env['calendar.event'].browse(event_id).exists())

    def test_07_expenses_and_payment_status(self):
        """Verify expense calculations and payment status security restriction."""
        now = fields.Datetime.now()
        req = self.env['fleet.dispatch.request'].create({
            'employee_id': self.employee_requester.id,
            'destination': 'Hai Duong',
            'purpose': 'Customer delivery',
            'start_datetime': now + timedelta(days=7),
            'end_datetime': now + timedelta(days=7, hours=4),
        })

        expense_toll = self.env['fleet.dispatch.expense'].create({
            'request_id': req.id,
            'expense_type': 'toll',
            'amount': 70000.0,
            'description': 'Expressway Toll',
        })
        expense_fuel = self.env['fleet.dispatch.expense'].create({
            'request_id': req.id,
            'expense_type': 'fuel',
            'amount': 500000.0,
            'description': 'Gasoline RON95',
        })

        self.assertEqual(req.total_expense_amount, 570000.0)

        # Regular user tries to mark payment_status = 'paid' -> AccessError
        with self.assertRaises(AccessError):
            expense_toll.with_user(self.user_requester).write({'payment_status': 'paid'})

        # Officer can mark payment_status = 'paid'
        expense_toll.with_user(self.user_officer).write({'payment_status': 'paid'})
        self.assertEqual(expense_toll.payment_status, 'paid')

    def test_08_immutability_and_unlink_security(self):
        """Verify done/cancelled trips are immutable to non-managers, and only managers can delete."""
        now = fields.Datetime.now()
        req = self.env['fleet.dispatch.request'].create({
            'employee_id': self.employee_requester.id,
            'destination': 'Hung Yen',
            'purpose': 'Partner visit',
            'start_datetime': now + timedelta(days=8),
            'end_datetime': now + timedelta(days=8, hours=3),
            'vehicle_id': self.vehicle_1.id,
            'driver_id': self.driver_partner.id,
            'odometer_start': 10000.0,
            'odometer_end': 10100.0,
            'state': 'done',
        })

        # Regular user and officer cannot modify done trip
        with self.assertRaises(UserError):
            req.with_user(self.user_requester).write({'destination': 'New Destination'})
        with self.assertRaises(UserError):
            req.with_user(self.user_officer).write({'destination': 'New Destination'})

        # Non-manager cannot delete trip
        with self.assertRaises(AccessError):
            req.with_user(self.user_officer).unlink()

        # Manager can delete trip
        req.with_user(self.user_manager).unlink()
        self.assertFalse(req.exists())

    def test_09_multicompany_isolation(self):
        """Verify multi-company isolation on dispatch requests."""
        now = fields.Datetime.now()
        req_c1 = self.env['fleet.dispatch.request'].create({
            'employee_id': self.employee_requester.id,
            'destination': 'Company 1 Trip',
            'purpose': 'Business C1',
            'start_datetime': now + timedelta(days=9),
            'end_datetime': now + timedelta(days=9, hours=2),
            'company_id': self.company.id,
        })

        # User in Company 2
        user_c2 = cls = self.env['res.users'].create({
            'name': 'User Company 2',
            'login': 'user_c2',
            'email': 'c2@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id, self.group_user.id])],
            'company_id': self.company_2.id,
            'company_ids': [(6, 0, [self.company_2.id])],
        })

        # Searching with user_c2 should not see Company 1's request
        c2_results = self.env['fleet.dispatch.request'].with_user(user_c2).search([('id', '=', req_c1.id)])
        self.assertEqual(len(c2_results), 0, "Company 2 user must not see Company 1 dispatch requests")
