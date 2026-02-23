# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LogilinkPaymentHeader(models.Model):
    _name = "logilink.payment.header"
    _description = "Payment Header"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "payment_date desc, id desc"
    _rec_name = "payment_reference"

    invoice_id = fields.Many2one("logilink.supplier.invoice.header", string="Invoice", required=True, help="Invoice being paid")
    payment_date = fields.Date("Payment Date", default=fields.Date.today, required=True, help="Date of payment")
    payment_method = fields.Selection([
        ("cash", "Cash"),
        ("check", "Check"),
        ("bank_transfer", "Bank Transfer"),
        ("credit_card", "Credit Card"),
        ("other", "Other")
    ], string="Payment Method", required=True, help="Method of payment")
    payment_reference = fields.Char("Payment Reference", help="Reference number for the payment (check number, transaction ID, etc.)")
    amount_paid = fields.Monetary("Amount Paid", currency_field="currency_id", required=True, help="Amount paid in this payment")
    balance_remaining = fields.Monetary("Balance Remaining", currency_field="currency_id", compute="_compute_balance", store=False, help="Remaining balance on the invoice")
    status = fields.Selection([
        ("partial", "Partial"),
        ("fully_paid", "Fully Paid")
    ], string="Status", compute="_compute_status", store=False, help="Payment status")
    currency_id = fields.Many2one("res.currency", string="Currency", related="invoice_id.currency_id", store=True, readonly=True)
    active = fields.Boolean(default=True, help="Archive/unarchive record")

    @api.depends("invoice_id", "invoice_id.total_invoice_amount", "invoice_id.payment_ids", "invoice_id.payment_ids.amount_paid", "amount_paid")
    def _compute_balance(self):
        """Compute remaining balance on invoice"""
        for rec in self:
            if rec.invoice_id:
                # Get total payments for this invoice
                total_payments = sum(rec.invoice_id.payment_ids.mapped("amount_paid") or [0])
                rec.balance_remaining = rec.invoice_id.total_invoice_amount - total_payments
            else:
                rec.balance_remaining = 0

    @api.depends("balance_remaining")
    def _compute_status(self):
        """Compute payment status"""
        for rec in self:
            if rec.balance_remaining and rec.balance_remaining > 0:
                rec.status = "partial"
            else:
                rec.status = "fully_paid"


# Add payment_ids field to invoice header
class LogilinkSupplierInvoiceHeader(models.Model):
    _inherit = "logilink.supplier.invoice.header"
    
    payment_ids = fields.One2many("logilink.payment.header", "invoice_id", string="Payments", help="Payments made against this invoice")
