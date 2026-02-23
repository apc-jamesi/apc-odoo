# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LogilinkSupplierInvoiceHeader(models.Model):
    _name = "logilink.supplier.invoice.header"
    _description = "Supplier Invoice Header"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "invoice_date desc, invoice_number desc"
    _rec_name = "invoice_number"

    invoice_number = fields.Char("Invoice Number", required=True, help="Supplier Invoice Number")
    supplier_id = fields.Many2one("res.partner", string="Supplier", required=True, help="Supplier who issued the invoice")
    po_id = fields.Many2one("logilink.purchase.order.header", string="Purchase Order", help="Related Purchase Order")
    invoice_date = fields.Date("Invoice Date", default=fields.Date.today, required=True, help="Date of the invoice")
    due_date = fields.Date("Due Date", help="Due date for payment")
    total_invoice_amount = fields.Monetary("Total Invoice Amount", currency_field="currency_id", compute="_compute_total_amount", store=True, help="Total amount of the invoice")
    match_status = fields.Selection([
        ("pending", "Pending"),
        ("matched", "Matched"),
        ("mismatch", "Mismatch"),
        ("on_hold", "On Hold")
    ], string="Match Status", default="pending", required=True, help="Status of invoice matching with PO")
    approval_status = fields.Selection([
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected")
    ], string="Approval Status", default="pending", required=True, help="Approval status of the invoice")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True, help="Archive/unarchive record")
    
    # Related fields
    line_ids = fields.One2many("logilink.supplier.invoice.line", "invoice_id", string="Invoice Lines", help="Items in this invoice")

    _sql_constraints = [
        ("invoice_number_unique", "unique(invoice_number)", "Invoice Number must be unique."),
    ]

    @api.depends("line_ids.line_total")
    def _compute_total_amount(self):
        """Compute total amount from all lines"""
        for rec in self:
            rec.total_invoice_amount = sum(rec.line_ids.mapped("line_total") or [0])


class LogilinkSupplierInvoiceLine(models.Model):
    _name = "logilink.supplier.invoice.line"
    _description = "Supplier Invoice Line"
    _order = "invoice_id, id"

    invoice_id = fields.Many2one("logilink.supplier.invoice.header", string="Invoice", required=True, ondelete="cascade", help="Invoice this line belongs to")
    po_line_id = fields.Many2one("logilink.purchase.order.line", string="PO Line", help="Related Purchase Order Line")
    quantity_invoiced = fields.Float("Quantity Invoiced", required=True, default=1.0, help="Quantity of items invoiced")
    unit_price = fields.Monetary("Unit Price", currency_field="currency_id", required=True, help="Price per unit")
    line_total = fields.Monetary("Line Total", currency_field="currency_id", compute="_compute_line_total", store=True, help="Total cost for this line")
    currency_id = fields.Many2one("res.currency", string="Currency", related="invoice_id.currency_id", store=True, readonly=True)

    @api.depends("quantity_invoiced", "unit_price")
    def _compute_line_total(self):
        """Compute line total from quantity and unit price"""
        for rec in self:
            rec.line_total = rec.quantity_invoiced * (rec.unit_price or 0)
