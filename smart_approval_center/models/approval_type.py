from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SmartApprovalType(models.Model):
    _name = "smart.approval.type"
    _description = "Approval Type"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    code = fields.Selection([
        ("expense", "Expense"), ("purchase", "Purchase"),
        ("advance", "Salary Advance"), ("other", "Other"),
    ], required=True, default="other")
    description = fields.Text()
    amount_required = fields.Boolean(default=True)
    min_amount = fields.Monetary(currency_field="currency_id", default=0.0)
    max_amount = fields.Monetary(currency_field="currency_id", help="Zero means no upper limit.")
    currency_id = fields.Many2one("res.currency", required=True,
        default=lambda self: self.env.company.currency_id)
    step_ids = fields.One2many("smart.approval.type.step", "type_id", string="Approvers")

    @api.constrains("min_amount", "max_amount")
    def _check_limits(self):
        for record in self:
            if record.min_amount < 0 or record.max_amount < 0:
                raise ValidationError(_("Limits cannot be negative."))
            if record.max_amount and record.max_amount < record.min_amount:
                raise ValidationError(_("Maximum amount must be greater than minimum."))


class SmartApprovalTypeStep(models.Model):
    _name = "smart.approval.type.step"
    _description = "Approval Type Step"
    _order = "sequence, id"

    type_id = fields.Many2one("smart.approval.type", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users", required=True, domain=[("share", "=", False)])

    _sql_constraints = [
        ("unique_user_per_type", "unique(type_id, user_id)",
         "The same user cannot approve twice in one approval type."),
    ]
