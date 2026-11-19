from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestSmartApproval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref("smart_approval_center.group_smart_approval_user")
        cls.requester = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Approval Requester", "login": "smart_approval_requester",
            "group_ids": [(4, cls.group_user.id)],
        })
        cls.approver = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Approval Reviewer", "login": "smart_approval_reviewer",
            "group_ids": [(4, cls.group_user.id)],
        })
        cls.type = cls.env["smart.approval.type"].create({
            "name": "General Expenses", "code": "expense",
            "step_ids": [(0, 0, {"name": "Manager review", "sequence": 10,
                                 "user_id": cls.approver.id})],
        })

    def _new_request(self):
        return self.env["smart.approval.request"].with_user(self.requester).create({
            "title": "Office supply request", "type_id": self.type.id,
            "amount": 200,
        })

    def test_approve_request(self):
        request = self._new_request()
        request.action_submit()
        self.assertEqual(request.state, "pending")
        self.assertEqual(request.current_approver_id, self.approver)
        request.with_user(self.approver).action_approve()
        self.assertEqual(request.state, "approved")
        self.assertTrue(request.date_closed)

    def test_only_current_reviewer_can_approve(self):
        request = self._new_request()
        request.action_submit()
        with self.assertRaises(AccessError):
            request.action_approve()

    def test_missing_approvers_blocks_submission(self):
        request = self._new_request()
        self.type.step_ids.unlink()
        with self.assertRaises(UserError):
            request.action_submit()

    def test_workflow_status_cannot_be_forged(self):
        request = self._new_request()
        with self.assertRaises(AccessError):
            request.with_user(self.requester).write({"state": "approved"})

    def test_reject_request(self):
        request = self._new_request()
        request.action_submit()
        request.with_user(self.approver).action_reject()
        self.assertEqual(request.state, "rejected")
