# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup
import base64

class LogilinkPurchaseOrderHeader(models.Model):
    _name = "logilink.purchase.order.header"
    _description = "Purchase Order Header"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "po_date desc, po_number desc"
    _rec_name = "po_number"

    po_number = fields.Char("PO Number", required=True, help="Purchase Order Number")
    pr_id = fields.Many2one("logilink.purchase.request.header", string="Purchase Request", help="Related Purchase Request")
    approver_id = fields.Many2one(
        "logilink.community",
        string="Approver",
        tracking=True,
        help="Approver for this Purchase Order (selected from Community).",
    )
    supplier_id = fields.Many2one("res.partner", string="Supplier", help="Supplier for this purchase order")
    po_date = fields.Date("PO Date", default=fields.Date.today, required=True, help="Purchase Order Date")
    status = fields.Selection(
        [
            ("requested", "Requested"),
            ("sent_supplier", "Sent to Supplier (Quotation)"),
            ("submitted_email", "Submitted for Approval via Email"),
            ("printed", "Printed"),
            ("approved", "Approved"),
            ("declined", "Declined"),
        ],
        string="Status",
        default="requested",
        required=True,
        tracking=True,
        help="Current status of the purchase order",
    )
    total_po_amount = fields.Monetary("Total PO Amount", currency_field="currency_id", compute="_compute_total_amount", store=True, help="Total amount of the purchase order")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True, help="Archive/unarchive record")
    
    # Related fields
    line_ids = fields.One2many("logilink.purchase.order.line", "po_id", string="PO Lines", help="Items in this purchase order")

    _sql_constraints = [
        ("po_number_unique", "unique(po_number)", "PO Number must be unique."),
    ]

    @api.onchange("pr_id")
    def _onchange_pr_id_set_approver(self):
        """If this PO is linked to a PR, default the PO approver from the PR approver."""
        for rec in self:
            if rec.pr_id and rec.pr_id.approver_id and not rec.approver_id:
                rec.approver_id = rec.pr_id.approver_id

    @api.depends("line_ids.line_total")
    def _compute_total_amount(self):
        """Compute total amount from all lines"""
        for rec in self:
            rec.total_po_amount = sum(rec.line_ids.mapped("line_total") or [0])

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_print_po(self):
        """Print PO as PDF from 'Sent to Supplier' path, then move to Printed."""
        self.ensure_one()

        if self.status != "sent_supplier":
            raise UserError(_("Only 'Sent to Supplier (Quotation)' purchase orders can be printed."))

        self.status = "printed"

        self.message_post(
            body=Markup(_("Purchase Order has been <strong>printed</strong>.")),
            subject=_("Purchase Order Printed: %s") % self.po_number,
        )

        # Call the report action to generate the PDF
        report = self.env.ref("apc_logilink.action_report_purchase_order")
        return report.report_action(self)

    def action_print_approved_po(self):
        """Print an already approved PO without changing its status."""
        self.ensure_one()

        if self.status != "approved":
            raise UserError(_("Only approved purchase orders can be printed from this action."))

        report = self.env.ref("apc_logilink.action_report_purchase_order")
        return report.report_action(self)

    def _mark_sent_supplier_after_email(self):
        """Advance to supplier-sent only after the supplier email is actually sent."""
        for rec in self:
            if rec.status != "requested":
                continue
            rec.status = "sent_supplier"
            rec.message_post(
                body=Markup(_("Purchase Order has been <strong>sent to supplier</strong> for quotation.")),
                subject=_("PO Sent to Supplier: %s") % rec.po_number,
            )

    def _mark_submitted_email_after_send(self):
        """Advance to approval-submitted only after the approval email is actually sent."""
        for rec in self:
            if rec.status != "sent_supplier":
                continue
            rec.status = "submitted_email"
            rec.message_post(
                body=Markup(_("Purchase Order has been <strong>submitted for approval via email</strong>.")),
                subject=_("PO Submitted via Email: %s") % rec.po_number,
            )

    def action_mark_sent_supplier(self):
        """Open a wizard that lets the user choose how to send the PO to the supplier."""
        self.ensure_one()

        if self.status != "requested":
            raise UserError(_("Only Requested purchase orders can be sent to supplier."))
        if not self.supplier_id:
            raise UserError(_("Please select a Supplier before continuing."))

        return {
            "name": _("Send Purchase Order to Supplier"),
            "type": "ir.actions.act_window",
            "res_model": "logilink.purchase.order.send.supplier.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_po_id": self.id},
        }

    def action_open_supplier_email_composer(self):
        """Prepare the supplier email composer with the PO PDF attached."""
        self.ensure_one()

        if self.status != "requested":
            raise UserError(_("Only Requested purchase orders can be sent to supplier."))

        if not self.supplier_id:
            raise UserError(_("Please select a Supplier before emailing."))
        if not self.supplier_id.email:
            raise UserError(_("The selected Supplier does not have an email address."))

        # Render PO PDF and attach it to the outgoing email.
        report_xmlid = "apc_logilink.action_report_purchase_order"
        pdf_content, report_type = (
            self.env["ir.actions.report"]
            .sudo()
            ._render_qweb_pdf(report_xmlid, [self.id])
        )
        attachment = self.env["ir.attachment"].sudo().create(
            {
                "name": f"{self.po_number}.pdf",
                "type": "binary",
                "datas": base64.b64encode(pdf_content),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/pdf",
            }
        )

        subject = _("Purchase Order %s") % (self.po_number or "")
        body_text = _("[Insert your message body here...]")
        default_email_from = self.env["ir.config_parameter"].sudo().get_param("mail.default.from")

        ctx = {
            "default_model": self._name,
            "default_res_ids": [self.id],
            "default_composition_mode": "comment",
            "default_subject": subject,
            "default_body": body_text,
            "default_partner_ids": [(6, 0, [self.supplier_id.id])],
            "force_email": True,
            "default_attachment_ids": [(6, 0, [attachment.id])],
            "form_view_ref": "mail.email_compose_message_wizard_form",
            "clicked_on_full_composer": True,
            "mark_po_sent_supplier_after_send": True,
        }
        if default_email_from:
            ctx["default_email_from"] = default_email_from

        return {
            "name": _("Send Purchase Order to Supplier"),
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": self.env.context.get("mail_composer_target", "new"),
            "context": ctx,
        }

    def action_download_supplier_pdf(self):
        """Download the supplier-facing PO PDF and advance to Sent to Supplier."""
        self.ensure_one()

        if self.status != "requested":
            raise UserError(_("Only Requested purchase orders can be downloaded from this action."))

        self.status = "sent_supplier"
        self.message_post(
            body=Markup(_("Purchase Order PDF has been <strong>downloaded</strong> for supplier quotation.")),
            subject=_("PO PDF Downloaded: %s") % self.po_number,
        )

        report = self.env.ref("apc_logilink.action_report_purchase_order")
        action = report.report_action(self)
        action["close_on_report_download"] = True
        return action

    def action_approve(self):
        """Approve PO and log in chatter."""
        self.ensure_one()

        if self.status not in ("submitted_email", "printed"):
            raise UserError(_("Only Email-submitted or Printed purchase orders can be approved."))

        self.status = "approved"
        self.message_post(
            body=Markup(_("Purchase Order has been <strong>approved</strong> and is now <strong>closed</strong>.")),
            subject=_("Purchase Order Approved: %s") % self.po_number,
        )
        return True

    def action_decline(self):
        """Decline PO and log in chatter."""
        self.ensure_one()

        if self.status not in ("submitted_email", "printed"):
            raise UserError(_("Only Email-submitted or Printed purchase orders can be declined."))

        self.status = "declined"
        self.message_post(
            body=Markup(_("Purchase Order has been <strong>declined</strong> and is now <strong>closed</strong>.")),
            subject=_("Purchase Order Declined: %s") % self.po_number,
        )
        return True

    # Backwards compatible alias (old button/action name)
    def action_mark_cancelled(self):
        """Deprecated: kept for compatibility; maps to Declined."""
        return self.action_decline()

    def action_mark_open(self):
        """Deprecated: kept for compatibility; maps to Requested."""
        self.ensure_one()
        self.status = "requested"
        return True

    def action_approve_with_message(self, message=""):
        """Approve PO and optionally log a message (used by email approval flow)."""
        self.ensure_one()
        self.action_approve()
        msg = (message or "").strip()
        if msg:
            self.message_post(
                body=Markup(msg),
                subject=_("Approver Message: %s") % self.po_number,
            )
        return True

    def action_decline_with_message(self, message=""):
        """Decline PO and optionally log a message (used by email approval flow)."""
        self.ensure_one()
        self.action_decline()
        msg = (message or "").strip()
        if msg:
            self.message_post(
                body=Markup(msg),
                subject=_("Approver Message: %s") % self.po_number,
            )
        return True

    def action_send_purchase_order_email(self):
        """Open mail composer to send Purchase Order approval email to the approver."""
        self.ensure_one()
        if self.status != "sent_supplier":
            raise UserError(_("You can only submit via email after the PO is sent to supplier."))

        email_body = self._generate_purchase_order_email_body(display_status="submitted_email")
        default_email_from = self.env["ir.config_parameter"].sudo().get_param("mail.default.from")

        partner_ids = []
        # Odoo's mail composer primarily targets res.partner recipients (partner_ids).
        # Our approver is stored in logilink.community, so we map it to a partner using the community email.
        if self.approver_id and getattr(self.approver_id, "email", False):
            email = (self.approver_id.email or "").strip()
            if email:
                partner = self.env["res.partner"].sudo().search([("email", "=", email)], limit=1)
                if not partner:
                    partner = self.env["res.partner"].sudo().create(
                        {
                            "name": self.approver_id.name or email,
                            "email": email,
                            "company_type": "person",
                        }
                    )
                partner_ids = [partner.id]

        ctx = {
            "default_model": "logilink.purchase.order.header",
            "default_res_ids": [self.id],
            "default_composition_mode": "comment",
            "default_subject": _("Purchase Order for Approval: %s") % self.po_number,
            "default_body": email_body,
            "default_email_layout_xmlid": "mail.mail_notification_layout_with_responsible_signature",
            "force_email": True,
            "form_view_ref": "mail.email_compose_message_wizard_form",
            "clicked_on_full_composer": True,
            "mark_po_submitted_email_after_send": True,
        }
        if default_email_from:
            ctx["default_email_from"] = default_email_from

        if partner_ids:
            ctx["default_partner_ids"] = [(6, 0, partner_ids)]
        elif self.approver_id and getattr(self.approver_id, "email", False):
            # Fallback: still set email_to (some views hide it, but it can still work for delivery).
            ctx["default_email_to"] = self.approver_id.email

        return {
            "name": _("Send Purchase Order for Approval"),
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }

    def _generate_purchase_order_email_body(self, display_status=None):
        """Generate formatted email body with Purchase Order information + action buttons."""
        self.ensure_one()
        display_status = display_status or self.status

        status_colors = {
            "requested": {"bg": "#f5f5f5", "border": "#9e9e9e", "badge_bg": "#757575", "badge_text": "#ffffff"},
            "sent_supplier": {"bg": "#e8eaf6", "border": "#5c6bc0", "badge_bg": "#5c6bc0", "badge_text": "#ffffff"},
            "submitted_email": {"bg": "#e3f2fd", "border": "#1976d2", "badge_bg": "#1976d2", "badge_text": "#ffffff"},
            "printed": {"bg": "#fff8e1", "border": "#f9a825", "badge_bg": "#f9a825", "badge_text": "#ffffff"},
            "approved": {"bg": "#e8f5e9", "border": "#4caf50", "badge_bg": "#4caf50", "badge_text": "#ffffff"},
            "declined": {"bg": "#ffebee", "border": "#f44336", "badge_bg": "#f44336", "badge_text": "#ffffff"},
        }
        status_info = status_colors.get(display_status, status_colors["requested"])

        body_parts = []
        body_parts.append(
            "<div style='font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif; max-width: 800px; margin: 0 auto; background-color: #ffffff; color: #212121;'>"
        )

        body_parts.append("<div style='background-color: #2c3e50; padding: 30px; color: #ffffff;'>")
        body_parts.append(
            "<h1 style='margin: 0; font-size: 28px; font-weight: 600; letter-spacing: -0.5px; color: #ffffff;'>Purchase Order</h1>"
        )
        body_parts.append("<p style='margin: 8px 0 0 0; font-size: 16px; color: #e0e0e0;'>Approval Required</p>")
        body_parts.append("</div>")

        status_label = Markup.escape(dict(self._fields["status"].selection).get(display_status, display_status))
        body_parts.append(
            f"<div style='padding: 20px 30px; background-color: {status_info['bg']}; border-left: 4px solid {status_info['border']}; margin: 20px 30px; border-radius: 4px;'>"
        )
        body_parts.append(
            f"<span style='display: inline-block; padding: 8px 16px; background-color: {status_info['badge_bg']}; color: {status_info['badge_text']}; border-radius: 20px; font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;'>{status_label}</span>"
        )
        body_parts.append("</div>")

        body_parts.append(
            "<div style='background-color: #f8f9fa; padding: 25px 30px; margin: 0 30px 20px 30px; border-radius: 8px; border: 1px solid #e0e0e0;'>"
        )
        body_parts.append(
            "<h2 style='color: #212121; margin: 0 0 20px 0; font-size: 20px; font-weight: 600;'><span style='display: inline-block; width: 4px; height: 24px; background-color: #2c3e50; border-radius: 2px; margin-right: 12px; vertical-align: middle;'></span>Order Details</h2>"
        )

        po_number = Markup.escape(self.po_number) if self.po_number else "N/A"
        po_date = str(self.po_date) if self.po_date else "N/A"
        supplier_name = Markup.escape(self.supplier_id.name) if self.supplier_id and self.supplier_id.name else "N/A"
        pr_number = (
            Markup.escape(self.pr_id.pr_number)
            if self.pr_id and getattr(self.pr_id, "pr_number", False)
            else "N/A"
        )

        body_parts.append("<table style='width: 100%; border-collapse: collapse;'>")
        body_parts.append(
            f"<tr><td style='padding: 12px 0; font-weight: 600; color: #424242; width: 180px; border-bottom: 1px solid #e0e0e0;'>PO Number</td><td style='padding: 12px 0; color: #212121; border-bottom: 1px solid #e0e0e0;'><strong style='color: #212121;'>{po_number}</strong></td></tr>"
        )
        body_parts.append(
            f"<tr><td style='padding: 12px 0; font-weight: 600; color: #424242; border-bottom: 1px solid #e0e0e0;'>PO Date</td><td style='padding: 12px 0; color: #212121; border-bottom: 1px solid #e0e0e0;'>{po_date}</td></tr>"
        )
        body_parts.append(
            f"<tr><td style='padding: 12px 0; font-weight: 600; color: #424242; border-bottom: 1px solid #e0e0e0;'>PR Number</td><td style='padding: 12px 0; color: #212121; border-bottom: 1px solid #e0e0e0;'>{pr_number}</td></tr>"
        )
        body_parts.append(
            f"<tr><td style='padding: 12px 0; font-weight: 600; color: #424242;'>Supplier</td><td style='padding: 12px 0; color: #212121;'>{supplier_name}</td></tr>"
        )
        body_parts.append("</table>")
        body_parts.append("</div>")

        # PO Lines
        if self.line_ids:
            body_parts.append(
                "<div style='background-color: #ffffff; padding: 25px 30px; margin: 0 30px 20px 30px; border-radius: 8px; border: 1px solid #e0e0e0;'>"
            )
            body_parts.append(
                "<h2 style='color: #212121; margin: 0 0 20px 0; font-size: 20px; font-weight: 600;'><span style='display: inline-block; width: 4px; height: 24px; background-color: #2c3e50; border-radius: 2px; margin-right: 12px; vertical-align: middle;'></span>Items</h2>"
            )
            body_parts.append("<table style='width: 100%; border-collapse: collapse; border: 1px solid #e0e0e0;'>")
            body_parts.append("<thead><tr style='background-color: #2c3e50;'>")
            body_parts.append(
                "<th style='padding: 14px; text-align: left; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #ffffff; border: 1px solid #1a252f;'>Item Description</th>"
            )
            body_parts.append(
                "<th style='padding: 14px; text-align: center; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #ffffff; border: 1px solid #1a252f;'>Quantity</th>"
            )
            body_parts.append(
                "<th style='padding: 14px; text-align: right; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #ffffff; border: 1px solid #1a252f;'>Unit Cost</th>"
            )
            body_parts.append(
                "<th style='padding: 14px; text-align: right; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #ffffff; border: 1px solid #1a252f;'>Line Total</th>"
            )
            body_parts.append("</tr></thead><tbody>")

            sym = self.currency_id.symbol if self.currency_id and self.currency_id.symbol else ""
            for idx, line in enumerate(self.line_ids):
                row_bg = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
                item_desc = Markup.escape(line.item_description) if line.item_description else "N/A"
                qty = line.quantity_ordered or 0.0
                unit = line.unit_price or 0.0
                total = line.line_total or (qty * unit)
                body_parts.append(f"<tr style='background-color: {row_bg};'>")
                body_parts.append(
                    f"<td style='padding: 14px; border-bottom: 1px solid #e0e0e0; color: #212121; border-left: 1px solid #e0e0e0;'>{item_desc}</td>"
                )
                body_parts.append(
                    f"<td style='padding: 14px; text-align: center; border-bottom: 1px solid #e0e0e0; color: #424242; border-left: 1px solid #e0e0e0;'>{qty:,.2f}</td>"
                )
                body_parts.append(
                    f"<td style='padding: 14px; text-align: right; border-bottom: 1px solid #e0e0e0; color: #424242; border-left: 1px solid #e0e0e0;'>{sym} {unit:,.2f}</td>"
                )
                body_parts.append(
                    f"<td style='padding: 14px; text-align: right; border-bottom: 1px solid #e0e0e0; color: #212121; font-weight: 600; border-left: 1px solid #e0e0e0;'>{sym} {total:,.2f}</td>"
                )
                body_parts.append("</tr>")

            body_parts.append("</tbody></table></div>")

        # Action buttons (only show if status allows)
        if display_status == "submitted_email":
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "http://localhost:8069")
            approve_url = f"{base_url}/purchase_order/{self.id}/approve"
            decline_url = f"{base_url}/purchase_order/{self.id}/decline"

            body_parts.append(
                "<div style='padding: 30px; margin: 20px 30px; background-color: #f5f5f5; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center;'>"
            )
            body_parts.append(
                "<h3 style='color: #212121; margin: 0 0 20px 0; font-size: 18px; font-weight: 600;'>Take Action</h3>"
            )
            body_parts.append("<div style='display: inline-block; margin: 0 10px;'>")
            body_parts.append(
                f"<a href='{approve_url}' style='display: inline-block; padding: 14px 32px; background-color: #4caf50; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px; border: none;'>✓ Approve</a>"
            )
            body_parts.append("</div>")
            body_parts.append("<div style='display: inline-block; margin: 0 10px;'>")
            body_parts.append(
                f"<a href='{decline_url}' style='display: inline-block; padding: 14px 32px; background-color: #f44336; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px; border: none;'>✗ Decline</a>"
            )
            body_parts.append("</div>")
            body_parts.append(
                "<p style='margin: 15px 0 0 0; color: #757575; font-size: 13px;'>Click a button above to approve or decline this purchase order. You can add a message when you click.</p>"
            )
            body_parts.append("</div>")

        body_parts.append(
            "<div style='padding: 20px 30px; text-align: center; color: #757575; font-size: 12px; border-top: 1px solid #e0e0e0; margin-top: 30px; background-color: #fafafa;'>"
        )
        body_parts.append("<p style='margin: 0; color: #757575;'>This email was automatically generated from the Purchase Order system.</p>")
        body_parts.append("</div>")
        body_parts.append("</div>")

        return Markup("".join(body_parts))

    def action_view_list_export(self):
        """Open list view for exporting data"""
        return {
            'name': 'Purchase Orders - Export',
            'type': 'ir.actions.act_window',
            'res_model': 'logilink.purchase.order.header',
            'view_mode': 'list',
            'view_id': False,
            'target': 'current',
            'context': self.env.context,
        }


class LogilinkPurchaseOrderLine(models.Model):
    _name = "logilink.purchase.order.line"
    _description = "Purchase Order Line"
    _order = "po_id, id"
    _rec_name = "item_description"

    po_id = fields.Many2one("logilink.purchase.order.header", string="Purchase Order", required=True, ondelete="cascade", help="Purchase Order this line belongs to")
    pr_line_id = fields.Many2one("logilink.purchase.request.line", string="PR Line", help="Related Purchase Request Line")
    # Read-only helpers to show PR line details in the PO lines UI (non-repetitive; source of truth is the PR line).
    pr_item_description = fields.Text(related="pr_line_id.item_description", readonly=True)
    pr_quantity_requested = fields.Float(related="pr_line_id.quantity_requested", readonly=True)
    pr_estimated_unit_cost = fields.Monetary(
        string="Unit Cost",
        related="pr_line_id.estimated_unit_cost",
        readonly=True,
        currency_field="currency_id",
    )
    pr_line_total = fields.Monetary(related="pr_line_id.line_total", readonly=True, currency_field="currency_id")
    pr_item_type = fields.Selection(related="pr_line_id.item_type", readonly=True)
    pr_line_summary = fields.Char(related="pr_line_id.line_summary", readonly=True)

    # These fields are still stored for reporting/printing and totals, but they are auto-filled from the PR line.
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

    @api.onchange("pr_line_id")
    def _onchange_pr_line_id_fill_fields(self):
        """When user selects a PR line, fill the stored PO-line fields automatically."""
        for rec in self:
            if not rec.pr_line_id:
                continue
            prl = rec.pr_line_id
            rec.item_description = prl.item_description
            rec.unit_price = prl.estimated_unit_cost or 0.0
            # Default to remaining qty if available; otherwise fall back to requested qty.
            qty = prl.remaining_qty if prl.remaining_qty is not None else prl.quantity_requested
            if qty and qty > 0:
                rec.quantity_ordered = qty

    @api.model_create_multi
    def create(self, vals_list):
        """Server-side safety: ensure required fields are set when only pr_line_id is provided."""
        pr_line_model = self.env["logilink.purchase.request.line"]
        for vals in vals_list:
            pr_line_id = vals.get("pr_line_id")
            if not pr_line_id:
                continue
            prl = pr_line_model.browse(pr_line_id)
            if not vals.get("item_description"):
                vals["item_description"] = prl.item_description
            if vals.get("unit_price") in (None, False):
                vals["unit_price"] = prl.estimated_unit_cost or 0.0
            if vals.get("quantity_ordered") in (None, False):
                qty = prl.remaining_qty if prl.remaining_qty is not None else prl.quantity_requested
                vals["quantity_ordered"] = qty or 0.0
        return super().create(vals_list)

    def name_get(self):
        """Human-readable label for PO lines (used e.g. in GRN PO Line selection)."""
        res = []
        for rec in self:
            desc = (rec.item_description or "").strip() or _("(No Description)")
            sym = rec.currency_id.symbol if rec.currency_id and rec.currency_id.symbol else ""
            qty = rec.quantity_ordered or 0.0
            unit = rec.unit_price or 0.0
            total = rec.line_total or (qty * unit)
            name = _(
                "%(desc)s | Qty: %(qty).2f | Unit: %(sym)s%(unit).2f | Total: %(sym)s%(total).2f"
            ) % {
                "desc": desc,
                "qty": qty,
                "sym": sym,
                "unit": unit,
                "total": total,
            }
            res.append((rec.id, name))
        return res

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Allow searching PO lines by description or PO number."""
        args = list(args or [])
        if name:
            domain = [
                "|",
                ("item_description", operator, name),
                ("po_id.po_number", operator, name),
            ]
            args = domain + args
        recs = self.search(args, limit=limit)
        return recs.name_get()

    @api.constrains("quantity_ordered", "pr_line_id")
    def _check_quantity_not_exceed_requested(self):
        """Ensure a PR line can be split across multiple PO lines but never exceeds requested qty."""
        for rec in self:
            if not rec.pr_line_id:
                continue
            if rec.quantity_ordered is None:
                continue

            # Ignore constraints for declined POs: declining should "release" the quantity.
            if rec.po_id and rec.po_id.status == "declined":
                continue

            pr_line = rec.pr_line_id
            other_lines = pr_line.po_line_ids.filtered(
                lambda l: l.id != rec.id and l.po_id and l.po_id.status != "declined"
            )
            total_ordered = sum(other_lines.mapped("quantity_ordered") or [0.0]) + (rec.quantity_ordered or 0.0)
            if (pr_line.quantity_requested or 0.0) < total_ordered - 1e-9:
                raise models.ValidationError(
                    _(
                        "Ordered quantity for a request line cannot exceed the requested quantity.\n"
                        "Requested: %(requested)s\n"
                        "Attempted total ordered: %(ordered)s"
                    )
                    % {"requested": pr_line.quantity_requested, "ordered": total_ordered}
                )
