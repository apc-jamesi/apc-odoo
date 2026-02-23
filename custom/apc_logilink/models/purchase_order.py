# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LogilinkPurchaseOrderHeader(models.Model):
    _name = "logilink.purchase.order.header"
    _description = "Purchase Order Header"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "po_date desc, po_number desc"
    _rec_name = "po_number"

    po_number = fields.Char("PO Number", required=True, help="Purchase Order Number")
    pr_id = fields.Many2one("logilink.purchase.request.header", string="Purchase Request", help="Related Purchase Request")
    supplier_id = fields.Many2one("res.partner", string="Supplier", required=True, help="Supplier for this purchase order")
    po_date = fields.Date("PO Date", default=fields.Date.today, required=True, help="Purchase Order Date")
    status = fields.Selection([
        ("open", "Open"),
        ("partial", "Partial"),
        ("closed", "Closed")
    ], string="Status", default="open", required=True, help="Current status of the purchase order")
    total_po_amount = fields.Monetary("Total PO Amount", currency_field="currency_id", compute="_compute_total_amount", store=True, help="Total amount of the purchase order")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True, help="Archive/unarchive record")
    
    # Related fields
    line_ids = fields.One2many("logilink.purchase.order.line", "po_id", string="PO Lines", help="Items in this purchase order")

    _sql_constraints = [
        ("po_number_unique", "unique(po_number)", "PO Number must be unique."),
    ]

    @api.depends("line_ids.line_total")
    def _compute_total_amount(self):
        """Compute total amount from all lines"""
        for rec in self:
            rec.total_po_amount = sum(rec.line_ids.mapped("line_total") or [0])


class LogilinkPurchaseOrderLine(models.Model):
    _name = "logilink.purchase.order.line"
    _description = "Purchase Order Line"
    _order = "po_id, id"

    po_id = fields.Many2one("logilink.purchase.order.header", string="Purchase Order", required=True, ondelete="cascade", help="Purchase Order this line belongs to")
    pr_line_id = fields.Many2one("logilink.purchase.request.line", string="PR Line", help="Related Purchase Request Line")
    item_description = fields.Text("Item Description", required=True, help="Description of the item ordered")
    quantity_ordered = fields.Float("Quantity Ordered", required=True, default=1.0, help="Quantity of items ordered")
    unit_price = fields.Monetary("Unit Price", currency_field="currency_id", required=True, help="Price per unit")
    line_total = fields.Monetary("Line Total", currency_field="currency_id", compute="_compute_line_total", store=True, help="Total cost for this line")
    currency_id = fields.Many2one("res.currency", string="Currency", related="po_id.currency_id", store=True, readonly=True)

    @api.depends("quantity_ordered", "unit_price")
    def _compute_line_total(self):
        """Compute line total from quantity and unit price"""
        for rec in self:
            rec.line_total = rec.quantity_ordered * (rec.unit_price or 0)
