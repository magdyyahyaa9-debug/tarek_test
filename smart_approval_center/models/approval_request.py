from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class SmartApprovalRequest(models.Model):
    _name = "smart.approval.request"
    _description = "Approval Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, required=True)
    title = fields.Char(required=True, tracking=True)
    description = fields.Text()
    requester_id = fields.Many2one("res.users", required=True,
        default=lambda self: self.env.user, readonly=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True,
        default=lambda self: self.env.company, readonly=True)
    type_id = fields.Many2one("smart.approval.type", required=True,
        domain=[("active", "=", True)], tracking=True)
    currency_id = fields.Many2one("res.currency", related="type_id.currency_id", store=True)
    amount = fields.Monetary(currency_field="currency_id", tracking=True)
    date_requested = fields.Datetime(readonly=True, copy=False)
    date_closed = fields.Datetime(readonly=True, copy=False)
    state = fields.Selection([
        ("draft", "Draft"), ("pending", "Pending"),
        ("approved", "Approved"), ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ], default="draft", required=True, tracking=True, copy=False)
    approval_line_ids = fields.One2many("smart.approval.line", "request_id", readonly=True, copy=False)
    current_approver_id = fields.Many2one("res.users", compute="_compute_current_approver", store=True)
    can_approve = fields.Boolean(compute="_compute_can_approve")
    rejection_reason = fields.Text(readonly=True, copy=False)

    @api.depends("approval_line_ids.state", "approval_line_ids.user_id", "state")
    def _compute_current_approver(self):
        for rec in self:
            line = rec.approval_line_ids.filtered(lambda ln: ln.state == "pending").sorted("sequence")[:1]
            rec.current_approver_id = line.user_id if rec.state == "pending" and line else False

    @api.depends("current_approver_id", "state")
    @api.depends_context("uid")
    def _compute_can_approve(self):
        for rec in self:
            rec.can_approve = rec.state == "pending" and rec.current_approver_id.id == self.env.uid

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not self.env.su and any(key in vals for key in (
                "state", "approval_line_ids", "date_closed", "date_requested",
                "rejection_reason", "name", "requester_id", "company_id")):
                raise AccessError(_("Protected request fields cannot be set manually."))
            vals["name"] = self.env["ir.sequence"].next_by_code("smart.approval.request") or "New"
            vals["requester_id"] = self.env.uid
            vals["company_id"] = self.env.company.id
        return super().create(vals_list)

    def write(self, vals):
        protected = {"state", "approval_line_ids", "date_closed", "date_requested",
                     "rejection_reason", "requester_id", "company_id", "name"}
        if not self.env.su and protected.intersection(vals):
            raise AccessError(_("Workflow fields may only change through approval actions."))
        if not self.env.su and any(rec.state != "draft" or rec.requester_id != self.env.user for rec in self):
            raise AccessError(_("Only the requester can edit a draft request."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and any(rec.state != "draft" or rec.requester_id != self.env.user for rec in self):
            raise AccessError(_("Only your draft requests may be deleted."))
        return super().unlink()

    @api.constrains("amount")
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("Amount cannot be negative."))

    def _check_requester(self):
        for rec in self:
            if rec.requester_id != self.env.user and not self.env.user.has_group(
                "smart_approval_center.group_smart_approval_manager"):
                raise AccessError(_("Only the requester can perform this action."))

    def _clear_approval_activities(self):
        self.sudo().activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref("mail.mail_activity_data_todo")
            and a.summary == "Approval required"
        ).unlink()

    def _notify_next_approver(self):
        for rec in self:
            if rec.current_approver_id:
                rec.sudo().activity_schedule(
                    "mail.mail_activity_data_todo", user_id=rec.current_approver_id.id,
                    summary="Approval required",
                    note=_("Please review request %s.") % rec.name,
                )

    def action_submit(self):
        self._check_requester()
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only drafts can be submitted."))
            approval_type = rec.type_id
            steps = approval_type.step_ids.sorted("sequence")
            if not steps:
                raise UserError(_("Configure at least one approver on the request type."))
            if approval_type.amount_required and rec.amount <= 0:
                raise UserError(_("Enter an amount greater than zero."))
            if rec.amount < approval_type.min_amount or (approval_type.max_amount and rec.amount > approval_type.max_amount):
                raise UserError(_("Amount falls outside the limits for this request type."))
            rec.sudo().write({
                "state": "pending", "date_requested": fields.Datetime.now(),
                "approval_line_ids": [(0, 0, {
                    "name": step.name, "user_id": step.user_id.id,
                    "sequence": step.sequence,
                }) for step in steps],
            })
            rec._notify_next_approver()

    def action_approve(self):
        for rec in self:
            if not rec.can_approve:
                raise AccessError(_("You are not the current approver."))
            line = rec.approval_line_ids.filtered(lambda ln: ln.state == "pending").sorted("sequence")[:1]
            if not line:
                raise UserError(_("No pending approval step found."))
            line.sudo().write({"state": "approved", "decision_date": fields.Datetime.now()})
            rec._clear_approval_activities()
            if not rec.approval_line_ids.filtered(lambda ln: ln.state == "pending"):
                rec.sudo().write({"state": "approved", "date_closed": fields.Datetime.now()})
            else:
                rec._notify_next_approver()
            rec.message_post(body=_("Approved by %s.") % self.env.user.name)

    def action_reject(self):
        for rec in self:
            if not rec.can_approve:
                raise AccessError(_("You are not the current approver."))
            rec.approval_line_ids.filtered(lambda ln: ln.state == "pending").sorted("sequence")[:1].sudo().write({
                "state": "rejected", "decision_date": fields.Datetime.now(),
            })
            rec.sudo().write({"state": "rejected", "date_closed": fields.Datetime.now()})
            rec._clear_approval_activities()
            rec.message_post(body=_("Rejected by %s.") % self.env.user.name)

    def action_cancel(self):
        self._check_requester()
        for rec in self:
            if rec.state not in ("draft", "pending"):
                raise UserError(_("Only draft or pending requests can be cancelled."))
            rec.sudo().write({"state": "cancelled", "date_closed": fields.Datetime.now()})
            rec._clear_approval_activities()


class SmartApprovalLine(models.Model):
    _name = "smart.approval.line"
    _description = "Approval Decision"
    _order = "sequence, id"

    request_id = fields.Many2one("smart.approval.request", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users", required=True)
    state = fields.Selection([
        ("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")
    ], default="pending", required=True)
    decision_date = fields.Datetime(readonly=True)
