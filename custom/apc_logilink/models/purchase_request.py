# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LogilinkPurchaseRequestHeader(models.Model):
    _name = "logilink.purchase.request.header"
    _description = "Purchase Request Header"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date_requested desc, pr_number desc"
    _rec_name = "pr_number"

    pr_number = fields.Char("PR Number", required=True, help="Purchase Request Number")
    date_requested = fields.Date("Date Requested", default=fields.Date.today, required=True, help="Date when the purchase request was made")
    department_id = fields.Many2one("logilink.department", string="Department", required=True, help="Department requesting the purchase")
    requested_by = fields.Many2one("res.users", string="Requested By", default=lambda self: self.env.user, required=True, help="Person who requested the purchase")
    date_needed = fields.Date("Date Needed", help="Date when the items are needed")
    status = fields.Selection([
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("converted", "Converted"),
        ("cancelled", "Cancelled")
    ], string="Status", default="draft", required=True, help="Current status of the purchase request")
    remarks = fields.Text("Remarks", help="Additional remarks or notes")
    active = fields.Boolean(default=True, help="Archive/unarchive record")
    
    # Related fields
    line_ids = fields.One2many("logilink.purchase.request.line", "pr_id", string="Request Lines", help="Items requested in this purchase request")
    total_amount = fields.Monetary("Total Amount", currency_field="currency_id", compute="_compute_total_amount", store=True, help="Total estimated amount of all lines")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ("pr_number_unique", "unique(pr_number)", "PR Number must be unique."),
    ]

    @api.depends("line_ids.line_total")
    def _compute_total_amount(self):
        """Compute total amount from all lines"""
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("line_total") or [0])


class LogilinkPurchaseRequestLine(models.Model):
    _name = "logilink.purchase.request.line"
    _description = "Purchase Request Line"
    _order = "pr_id, id"

    pr_id = fields.Many2one("logilink.purchase.request.header", string="Purchase Request", required=True, ondelete="cascade", help="Purchase Request this line belongs to")
    item_description = fields.Text("Item Description", required=True, help="Description of the item requested")
    quantity_requested = fields.Float("Quantity Requested", required=True, default=1.0, help="Quantity of items requested")
    estimated_unit_cost = fields.Monetary("Estimated Unit Cost", currency_field="currency_id", help="Estimated cost per unit")
    line_total = fields.Monetary("Line Total", currency_field="currency_id", compute="_compute_line_total", store=True, help="Total cost for this line")
    item_type = fields.Selection([
        ("asset", "Asset"),
        ("consumable", "Consumable"),
        ("service", "Service")
    ], string="Item Type", required=True, default="consumable", help="Type of item being requested")
    currency_id = fields.Many2one("res.currency", string="Currency", related="pr_id.currency_id", store=True, readonly=True)

    @api.depends("quantity_requested", "estimated_unit_cost")
    def _compute_line_total(self):
        """Compute line total from quantity and unit cost"""
        for rec in self:
            rec.line_total = rec.quantity_requested * (rec.estimated_unit_cost or 0)
