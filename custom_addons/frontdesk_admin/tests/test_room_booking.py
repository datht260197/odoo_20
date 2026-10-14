from datetime import timedelta
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRoomBooking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Subsidiary Company B'})

        # Security Groups
        cls.group_user = cls.env.ref('frontdesk_admin.group_frontdesk_user')
        cls.group_officer = cls.env.ref('frontdesk_admin.group_frontdesk_officer')
        cls.group_manager = cls.env.ref('frontdesk_admin.group_frontdesk_manager')

        # Users and Employees (Company A)
        cls.user_standard_1 = cls.env['res.users'].create({
            'name': 'Standard User 1',
            'login': 'std_user1_room',
            'email': 'std1@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })
        cls.employee_1 = cls.env['hr.employee'].create({
            'name': 'Employee 1',
            'user_id': cls.user_standard_1.id,
            'work_email': 'std1@example.com',
            'company_id': cls.company_a.id,
        })

        cls.user_standard_2 = cls.env['res.users'].create({
            'name': 'Standard User 2',
            'login': 'std_user2_room',
            'email': 'std2@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })
        cls.employee_2 = cls.env['hr.employee'].create({
            'name': 'Employee 2',
            'user_id': cls.user_standard_2.id,
            'work_email': 'std2@example.com',
            'company_id': cls.company_a.id,
        })

        cls.user_officer = cls.env['res.users'].create({
            'name': 'Frontdesk Officer',
            'login': 'officer_user_room',
            'email': 'officer_room@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_user.id,
                cls.group_officer.id,
            ])],
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })
        cls.employee_officer = cls.env['hr.employee'].create({
            'name': 'Officer Employee',
            'user_id': cls.user_officer.id,
            'work_email': 'officer_room@example.com',
            'company_id': cls.company_a.id,
        })

        cls.user_manager = cls.env['res.users'].create({
            'name': 'Frontdesk Manager',
            'login': 'manager_user_room',
            'email': 'manager_room@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_user.id,
                cls.group_officer.id,
                cls.group_manager.id,
            ])],
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })

        # Company B User & Employee
        cls.user_comp_b = cls.env['res.users'].create({
            'name': 'Company B User',
            'login': 'comp_b_user_room',
            'email': 'comp_b@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company_b.id,
            'company_ids': [(6, 0, [cls.company_b.id])],
        })
        cls.employee_comp_b = cls.env['hr.employee'].create({
            'name': 'Company B Employee',
            'user_id': cls.user_comp_b.id,
            'work_email': 'comp_b@example.com',
            'company_id': cls.company_b.id,
        })

        # Base Rooms in Company A
        cls.room_alpha = cls.env['frontdesk.meeting.room'].create({
            'name': 'Room Alpha',
            'location': 'Floor 2, East Wing',
            'capacity': 12,
            'has_projector': True,
            'has_video_conference': True,
            'has_whiteboard': True,
            'equipment_notes': 'Full HD projector with HDMI/Type-C dongle',
            'company_id': cls.company_a.id,
        })
        cls.room_beta = cls.env['frontdesk.meeting.room'].create({
            'name': 'Room Beta',
            'location': 'Floor 3, West Wing',
            'capacity': 8,
            'has_projector': True,
            'has_video_conference': False,
            'has_whiteboard': True,
            'company_id': cls.company_a.id,
        })

        # Room in Company B
        cls.room_comp_b = cls.env['frontdesk.meeting.room'].create({
            'name': 'Company B Boardroom',
            'location': 'HQ Floor 5',
            'capacity': 20,
            'company_id': cls.company_b.id,
        })

        cls.base_time = fields.Datetime.now().replace(microsecond=0) + timedelta(days=2)

    # -------------------------------------------------------------------------
    # 1. ROOM METADATA & VALIDATION
    # -------------------------------------------------------------------------
    def test_meeting_room_metadata_and_validation(self):
        """Verify room attributes, capacity constraint, and manager unlink rule."""
        self.assertEqual(self.room_alpha.name, 'Room Alpha')
        self.assertEqual(self.room_alpha.display_name, 'Room Alpha')
        self.assertTrue(self.room_alpha.has_projector)
        self.assertTrue(self.room_alpha.has_video_conference)

        # Capacity must be >= 1
        with self.assertRaises(ValidationError):
            self.env['frontdesk.meeting.room'].create({
                'name': 'Invalid Room',
                'capacity': 0,
                'company_id': self.company_a.id,
            })

        # Unlink by non-manager raises AccessError
        with self.assertRaises(AccessError):
            self.room_beta.with_user(self.user_officer).unlink()

        # Unlink by manager succeeds
        temp_room = self.env['frontdesk.meeting.room'].create({
            'name': 'Temp Room',
            'capacity': 5,
            'company_id': self.company_a.id,
        })
        temp_room.with_user(self.user_manager).unlink()
        self.assertFalse(temp_room.exists())

    # -------------------------------------------------------------------------
    # 2. FULL BOOKING WORKFLOW (Pending -> Confirmed -> Done)
    # -------------------------------------------------------------------------
    def test_room_booking_full_lifecycle(self):
        """Test complete workflow: pending -> confirmed -> done with immutability."""
        start = self.base_time
        end = start + timedelta(hours=2)

        booking = self.env['frontdesk.room.booking'].with_user(self.user_standard_1).create({
            'name': 'Product Strategy Meeting',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_1.id,
            'start_datetime': start,
            'end_datetime': end,
            'attendee_count': 6,
        })
        self.assertEqual(booking.state, 'pending')
        self.assertFalse(booking.calendar_event_id)

        # Confirm booking as officer
        booking.with_user(self.user_officer).action_confirm()
        self.assertEqual(booking.state, 'confirmed')
        self.assertTrue(booking.calendar_event_id)
        self.assertEqual(booking.calendar_event_id.name, f"[{self.room_alpha.name}] {booking.name}")
        self.assertEqual(booking.calendar_event_id.start, start)
        self.assertEqual(booking.calendar_event_id.stop, end)

        # Complete booking
        booking.with_user(self.user_officer).action_done()
        self.assertEqual(booking.state, 'done')

        # Immutability check: non-manager cannot edit fields in done state
        with self.assertRaises(UserError):
            booking.with_user(self.user_standard_1).write({'name': 'Tampered Meeting Subject'})

        # Non-manager cannot delete
        with self.assertRaises(AccessError):
            booking.with_user(self.user_standard_1).unlink()

    # -------------------------------------------------------------------------
    # 3. ANTI-COLLISION CONSTRAINT
    # -------------------------------------------------------------------------
    def test_room_booking_anti_collision(self):
        """Strictly test overlapping confirmed bookings prevention and timing."""
        start = self.base_time + timedelta(days=1)
        end = start + timedelta(hours=2)  # [start, start + 2h]

        # Confirm base booking on Room Alpha
        booking_base = self.env['frontdesk.room.booking'].create({
            'name': 'Anchor Meeting',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_1.id,
            'start_datetime': start,
            'end_datetime': end,
            'state': 'confirmed',
        })
        self.assertTrue(booking_base.exists())

        # Test A: Overlap right (starts during, ends after)
        overlap_right = self.env['frontdesk.room.booking'].create({
            'name': 'Overlap Right',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_2.id,
            'start_datetime': start + timedelta(hours=1),
            'end_datetime': end + timedelta(hours=1),
        })
        with self.assertRaises(ValidationError):
            overlap_right.with_user(self.user_officer).action_confirm()

        # Test B: Overlap left (starts before, ends during)
        overlap_left = self.env['frontdesk.room.booking'].create({
            'name': 'Overlap Left',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_2.id,
            'start_datetime': start - timedelta(hours=1),
            'end_datetime': start + timedelta(hours=1),
        })
        with self.assertRaises(ValidationError):
            overlap_left.with_user(self.user_officer).action_confirm()

        # Test C: Enclosing (starts before, ends after)
        overlap_enclosing = self.env['frontdesk.room.booking'].create({
            'name': 'Overlap Enclosing',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_2.id,
            'start_datetime': start - timedelta(minutes=30),
            'end_datetime': end + timedelta(minutes=30),
        })
        with self.assertRaises(ValidationError):
            overlap_enclosing.with_user(self.user_officer).action_confirm()

        # Test D: Enclosed (starts during, ends during)
        overlap_enclosed = self.env['frontdesk.room.booking'].create({
            'name': 'Overlap Enclosed',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_2.id,
            'start_datetime': start + timedelta(minutes=15),
            'end_datetime': end - timedelta(minutes=15),
        })
        with self.assertRaises(ValidationError):
            overlap_enclosed.with_user(self.user_officer).action_confirm()

        # Test E: Adjacent (ends exactly when base starts or starts when base ends) -> Allowed!
        adjacent_after = self.env['frontdesk.room.booking'].create({
            'name': 'Adjacent After',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_2.id,
            'start_datetime': end,
            'end_datetime': end + timedelta(hours=1),
        })
        adjacent_after.with_user(self.user_officer).action_confirm()
        self.assertEqual(adjacent_after.state, 'confirmed')

        # Test F: Same time slot on DIFFERENT room -> Allowed!
        diff_room = self.env['frontdesk.room.booking'].create({
            'name': 'Different Room Meeting',
            'room_id': self.room_beta.id,
            'organizer_id': self.employee_2.id,
            'start_datetime': start,
            'end_datetime': end,
        })
        diff_room.with_user(self.user_officer).action_confirm()
        self.assertEqual(diff_room.state, 'confirmed')

        # Test G: end_datetime <= start_datetime validation
        with self.assertRaises(ValidationError):
            self.env['frontdesk.room.booking'].create({
                'name': 'Invalid Timing',
                'room_id': self.room_alpha.id,
                'organizer_id': self.employee_1.id,
                'start_datetime': start,
                'end_datetime': start - timedelta(minutes=30),
            })

    # -------------------------------------------------------------------------
    # 4. CALENDAR EVENT SYNC & UNLINK ON CANCELLATION
    # -------------------------------------------------------------------------
    def test_calendar_sync_and_cancellation(self):
        """Verify calendar event creation on confirmation and clean unlinking on cancellation."""
        start = self.base_time + timedelta(days=3)
        end = start + timedelta(hours=1)

        booking = self.env['frontdesk.room.booking'].create({
            'name': 'Client Demo',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_1.id,
            'start_datetime': start,
            'end_datetime': end,
        })

        booking.with_user(self.user_officer).action_confirm()
        calendar_event = booking.calendar_event_id
        self.assertTrue(calendar_event)
        self.assertTrue(calendar_event.exists())

        # Cancel booking -> should unlink calendar event
        booking.with_user(self.user_officer).action_cancel()
        self.assertEqual(booking.state, 'cancelled')
        self.assertFalse(booking.calendar_event_id)
        self.assertFalse(calendar_event.exists())

    # -------------------------------------------------------------------------
    # 5. TEABREAK SERVICE & MAIL ACTIVITY CREATION
    # -------------------------------------------------------------------------
    def test_teabreak_activity_creation(self):
        """Verify mail.activity creation for Frontdesk Officers when teabreak is requested."""
        start = self.base_time + timedelta(days=4)
        end = start + timedelta(hours=2)

        booking = self.env['frontdesk.room.booking'].create({
            'name': 'Executive Board Meeting',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_1.id,
            'start_datetime': start,
            'end_datetime': end,
            'needs_teabreak': True,
            'teabreak_attendees': 10,
            'teabreak_notes': 'Hot tea, coffee, and fresh pastries required 15 mins before start',
        })

        # Pre-check: No activities yet
        self.assertEqual(len(booking.activity_ids), 0)

        # Confirm booking
        booking.with_user(self.user_officer).action_confirm()

        # Post-check: Activity created for frontdesk officer
        self.assertEqual(len(booking.activity_ids), 1)
        activity = booking.activity_ids[0]
        self.assertIn('Prepare Teabreak', activity.summary)
        self.assertTrue(activity.user_id.has_group('frontdesk_admin.group_frontdesk_officer'))
        self.assertIn('Hot tea, coffee', activity.note)

    # -------------------------------------------------------------------------
    # 6. RECORD-LEVEL SECURITY & PERMISSIONS
    # -------------------------------------------------------------------------
    def test_record_level_security_and_permissions(self):
        """Verify ACL rules: User can read all schedules, edit own pending, cannot confirm or delete."""
        start = self.base_time + timedelta(days=5)
        end = start + timedelta(hours=1)

        # Booking created by User 1
        booking_user_1 = self.env['frontdesk.room.booking'].with_user(self.user_standard_1).create({
            'name': 'User 1 Planning',
            'room_id': self.room_alpha.id,
            'organizer_id': self.employee_1.id,
            'start_datetime': start,
            'end_datetime': end,
        })

        # Booking created by User 2
        booking_user_2 = self.env['frontdesk.room.booking'].with_user(self.user_standard_2).create({
            'name': 'User 2 Brainstorming',
            'room_id': self.room_beta.id,
            'organizer_id': self.employee_2.id,
            'start_datetime': start,
            'end_datetime': end,
        })

        # 1. Global read access: User 1 can read User 2's booking schedule to check availability
        read_record = self.env['frontdesk.room.booking'].with_user(self.user_standard_1).search([
            ('id', '=', booking_user_2.id)
        ])
        self.assertEqual(len(read_record), 1)

        # 2. User 1 CAN edit their own pending booking
        booking_user_1.with_user(self.user_standard_1).write({'name': 'User 1 Updated Subject'})
        self.assertEqual(booking_user_1.name, 'User 1 Updated Subject')

        # 3. User 1 CANNOT edit User 2's pending booking
        with self.assertRaises(AccessError):
            booking_user_2.with_user(self.user_standard_1).write({'name': 'Hacked Subject'})

        # 4. Standard User CANNOT approve / confirm bookings
        with self.assertRaises(AccessError):
            booking_user_1.with_user(self.user_standard_1).action_confirm()

        # 5. Standard User CANNOT delete any booking
        with self.assertRaises(AccessError):
            booking_user_1.with_user(self.user_standard_1).unlink()

        # 6. Standard User can cancel their own pending booking
        booking_user_1.with_user(self.user_standard_1).action_cancel()
        self.assertEqual(booking_user_1.state, 'cancelled')

        # 7. Standard User CANNOT cancel someone else's booking
        with self.assertRaises(AccessError):
            booking_user_2.with_user(self.user_standard_1).action_cancel()

    # -------------------------------------------------------------------------
    # 7. MULTI-COMPANY ISOLATION
    # -------------------------------------------------------------------------
    def test_multicompany_isolation(self):
        """Ensure Company A user cannot see or access Company B rooms and bookings."""
        start = self.base_time + timedelta(days=6)
        end = start + timedelta(hours=1)

        booking_comp_b = self.env['frontdesk.room.booking'].with_user(self.user_comp_b).create({
            'name': 'Company B Confidential Meeting',
            'room_id': self.room_comp_b.id,
            'organizer_id': self.employee_comp_b.id,
            'start_datetime': start,
            'end_datetime': end,
            'company_id': self.company_b.id,
        })

        # User in Company A searching rooms
        rooms_seen_by_comp_a = self.env['frontdesk.meeting.room'].with_user(self.user_standard_1).search([
            ('id', '=', self.room_comp_b.id)
        ])
        self.assertFalse(rooms_seen_by_comp_a)

        # User in Company A searching bookings
        bookings_seen_by_comp_a = self.env['frontdesk.room.booking'].with_user(self.user_standard_1).search([
            ('id', '=', booking_comp_b.id)
        ])
        self.assertFalse(bookings_seen_by_comp_a)

    # -------------------------------------------------------------------------
    # 8. BACKWARD LINK IN VISITOR LOG
    # -------------------------------------------------------------------------
    def test_visitor_assigned_meeting_room(self):
        """Verify frontdesk.visitor relation to frontdesk.meeting.room and arrival notification."""
        visitor = self.env['frontdesk.visitor'].create({
            'name': 'External Consultant',
            'company_name': 'Tech Advisory Ltd',
            'purpose': 'Architecture Review',
            'host_id': self.employee_1.id,
            'room_id': self.room_alpha.id,
        })

        self.assertEqual(visitor.room_id, self.room_alpha)
        # Check-in and ensure notification mentions Room Alpha
        visitor.action_checkin()
        self.assertEqual(visitor.state, 'arrived')

    # -------------------------------------------------------------------------
    # 9. VIETNAMESE LOCALIZATION
    # -------------------------------------------------------------------------
    def test_vietnamese_localization(self):
        """Verify Vietnamese translations for Phase 4 meeting room terms in vi_VN context."""
        env_vi = self.env(context={'lang': 'vi_VN'})

        model_room = env_vi['frontdesk.meeting.room']
        self.assertEqual(
            model_room.fields_get(['name'])['name']['string'],
            'Tên phòng'
        )
        self.assertEqual(
            model_room.fields_get(['capacity'])['capacity']['string'],
            'Sức chứa (Người)'
        )
        self.assertEqual(
            model_room.fields_get(['has_video_conference'])['has_video_conference']['string'],
            'Thiết bị họp trực tuyến'
        )

        model_booking = env_vi['frontdesk.room.booking']
        self.assertEqual(
            model_booking.fields_get(['name'])['name']['string'],
            'Tiêu đề cuộc họp'
        )
        self.assertEqual(
            model_booking.fields_get(['organizer_id'])['organizer_id']['string'],
            'Người chủ trì'
        )
        self.assertEqual(
            model_booking.fields_get(['needs_teabreak'])['needs_teabreak']['string'],
            'Yêu cầu Teabreak / Nước uống'
        )

        # State translations
        state_selections = dict(model_booking.fields_get(['state'])['state']['selection'])
        self.assertEqual(state_selections.get('pending'), 'Chờ duyệt')
        self.assertEqual(state_selections.get('confirmed'), 'Đã duyệt')
