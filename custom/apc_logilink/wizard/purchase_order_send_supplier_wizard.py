# -*- coding: utf-8 -*-
from odoo import fields, models


class LogilinkPurchaseOrderSendSupplierWizard(models.TransientModel):
    _name = "logilink.purchase.order.send.supplier.wizard"
    _description = "Send Purchase Order to Supplier"

    po_id = fields.Many2one(
        "logilink.purchase.order.header",
        string="Purchase Order",
        required=True,
        readonly=True,
    )
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        related="po_id.supplier_id",
        readonly=True,
    )
    supplier_email = fields.Char(
        string="Supplier Email",
        related="po_id.supplier_id.email",
        readonly=True,
    )

    def action_send_email(self):
        self.ensure_one()
        return self.po_id.action_open_supplier_email_composer()

    def action_download_pdf(self):
        self.ensure_one()
        return self.po_id.action_download_supplier_pdf()
