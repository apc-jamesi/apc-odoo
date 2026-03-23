# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from markupsafe import Markup

class LogilinkPurchaseRequestHeader(models.Model):
    _name = "logilink.purchase.request.header"
    _description = "Purchase Request Header"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date_requested desc, pr_number desc"
    _rec_name = "pr_number"

    @api.model
    def _default_requested_by_community(self):
        """Default to a community member matching the current user's email, when available."""
        email = (self.env.user.partner_id.email or "").strip()
        if not email:
            return False
        return self.env["logilink.community"].search([("email", "=", email)], limit=1)

    pr_number = fields.Char("PR Number", required=True, help="Purchase Request Number")
    date_requested = fields.Date("Date Requested", default=fields.Date.today, required=True, help="Date when the purchase request was made")
    department_id = fields.Many2one("logilink.department", string="Department", required=True, help="Department requesting the purchase")
    # Legacy field kept to avoid destructive schema remap issues during upgrades.
    requested_by = fields.Many2one(
        "res.users",
        string="Requested By (Legacy User)",
        default=lambda self: self.env.user,
        required=True,
        help="Legacy requester user field kept for compatibility.",
    )
    requested_by_community_id = fields.Many2one(
        "logilink.community",
        string="Requested By",
        default=_default_requested_by_community,
        required=True,
        help="Community member who requested the purchase",
    )
    approver_id = fields.Many2one(
        "logilink.community",
        string="Approver",
        tracking=True,
        help="Approver (selected from Community).",
    )
    date_needed = fields.Date("Date Needed", help="Date when the items are needed")
    status = fields.Selection([
        ("requested", "Requested"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("declined", "Declined")
    ], string="Status", default="requested", required=True, help="Current status of the purchase request")
    remarks = fields.Text("Remarks", help="Additional remarks or notes")
    active = fields.Boolean(default=True, help="Archive/unarchive record")
    
    # Related fields
    line_ids = fields.One2many("logilink.purchase.request.line", "pr_id", string="Request Lines", help="Items requested in this purchase request")
    po_ids = fields.One2many("logilink.purchase.order.header", "pr_id", string="Purchase Orders", help="Purchase Orders created from this Purchase Request")
    po_count = fields.Integer(string="Purchase Orders", compute="_compute_po_count", store=True)
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

    @api.depends("po_ids")
    def _compute_po_count(self):
        for rec in self:
            rec.po_count = len(rec.po_ids)

    def write(self, vals):
        """Override write to auto-create PO when status changes to approved"""
        # Store original statuses before write
        status_changes = {}
        if 'status' in vals and vals['status'] == 'approved':
            for rec in self:
                status_changes[rec.id] = rec.status
        
        result = super().write(vals)
        
        # Check if status was changed to 'approved' (from a different status)
        if 'status' in vals and vals['status'] == 'approved':
            for rec in self:
                original_status = status_changes.get(rec.id)
                # Only create PO if status was changed from non-approved to approved
                if original_status and original_status != 'approved':
                    # Check if PO already exists
                    existing_po = self.env['logilink.purchase.order.header'].search([
                        ('pr_id', '=', rec.id)
                    ], limit=1)
                    
                    if not existing_po:
                        # Create PO automatically
                        rec._create_purchase_order_from_request()
        
        return result

    def action_approve_with_message(self, message=''):
        """Approve purchase request and add message to remarks"""
        self.ensure_one()
        if self.status not in ['requested', 'submitted']:
            raise ValueError(_('Only Requested or Submitted requests can be approved.'))
        
        # Update remarks with the message
        if message:
            # Just append the approver's response, no timestamp or labels
            if self.remarks:
                self.remarks += f"\n\n{message}"
            else:
                self.remarks = message
        
        # Update status
        self.status = 'approved'
        
        # Automatically create Purchase Order
        self._create_purchase_order_from_request()
        
        # Post message to chatter
        body_text = _('Purchase Request has been <strong>approved</strong>%s') % (
            f' with message: {message}' if message else ''
        )
        self.message_post(
            body=Markup(body_text),
            subject=_('Purchase Request Approved: %s') % self.pr_number
        )

    def _create_purchase_order_from_request(self):
        """Automatically create a Purchase Order from this Purchase Request.

        This preserves the existing behavior: on approval, a single PO is auto-created
        only if one does not already exist for this PR. Additional POs can be created
        via the dedicated user flow (wizard/button).
        """
        self.ensure_one()
        
        # Check if PO already exists for this PR
        existing_po = self.env['logilink.purchase.order.header'].search([
            ('pr_id', '=', self.id)
        ], limit=1)
        
        if existing_po:
            # PO already exists, don't create duplicate
            return existing_po
        
        # Generate PO number (using PR number as base or create new)
        po_number = f"PO-{self.pr_number}" if self.pr_number else f"PO-{fields.Date.today().strftime('%Y%m%d')}-{self.id}"
        
        # Ensure PO number is unique
        counter = 1
        base_po_number = po_number
        while self.env['logilink.purchase.order.header'].search([('po_number', '=', po_number)], limit=1):
            po_number = f"{base_po_number}-{counter}"
            counter += 1
        
        # Create Purchase Order Header (supplier can be added later)
        po_vals = {
            'po_number': po_number,
            'pr_id': self.id,
            'supplier_id': False,  # Supplier can be added later in the PO
            'po_date': fields.Date.today(),
            'status': 'requested',
            'currency_id': self.currency_id.id,
            'active': True,
        }
        
        try:
            po = self.env['logilink.purchase.order.header'].create(po_vals)
        except Exception as e:
            # If creation fails, log and re-raise
            self.message_post(
                body=_('Failed to automatically create Purchase Order: %s') % str(e),
                subject=_('PO Creation Error')
            )
            raise
        
        # Create Purchase Order Lines from Purchase Request Lines
        # Only include lines that still have remaining quantity (prevents duplicates when re-triggered).
        for pr_line in self.line_ids.filtered(lambda l: (l.remaining_qty or 0.0) > 0):
            po_line_vals = {
                'po_id': po.id,
                'pr_line_id': pr_line.id,
                'item_description': pr_line.item_description,
                'quantity_ordered': pr_line.remaining_qty,
                'unit_price': pr_line.estimated_unit_cost or 0.0,
                'currency_id': self.currency_id.id,
            }
            self.env['logilink.purchase.order.line'].create(po_line_vals)
        
        # Post message to PR chatter about PO creation
        body_text = _('Purchase Order <strong>%s</strong> has been automatically created from this Purchase Request.') % po.po_number
        self.message_post(
            body=Markup(body_text),
            subject=_('Purchase Order Created: %s') % po.po_number
        )
        
        return po

    def action_view_purchase_orders(self):
        """Smart button action: open Purchase Orders linked to this Purchase Request."""
        self.ensure_one()
        return {
            "name": _("Purchase Orders"),
            "type": "ir.actions.act_window",
            "res_model": "logilink.purchase.order.header",
            "view_mode": "list,form",
            "domain": [("pr_id", "=", self.id)],
            "context": {"default_pr_id": self.id},
        }

    def action_decline_with_message(self, message=''):
        """Decline purchase request and add message to remarks"""
        self.ensure_one()
        if self.status not in ['requested', 'submitted']:
            raise ValueError(_('Only Requested or Submitted requests can be declined.'))
        
        # Update remarks with the message
        if message:
            # Just append the approver's response, no timestamp or labels
            if self.remarks:
                self.remarks += f"\n\n{message}"
            else:
                self.remarks = message
        
        # Update status
        self.status = 'declined'
        
        # Post message to chatter
        body_text = _('Purchase Request has been <strong>declined</strong>%s') % (
            f' with message: {message}' if message else ''
        )
        self.message_post(
            body=Markup(body_text),
            subject=_('Purchase Request Declined: %s') % self.pr_number
        )

    def action_view_list_export(self):
        """Open list view for exporting data"""
        return {
            'name': 'Purchase Requests - Export',
            'type': 'ir.actions.act_window',
            'res_model': 'logilink.purchase.request.header',
            'view_mode': 'list',
            'view_id': False,
            'target': 'current',
            'context': self.env.context,
        }

    def action_decline(self):
        """Decline purchase request from UI (without message)"""
        self.ensure_one()
        if self.status not in ['requested', 'submitted']:
            raise ValueError(_('Only Requested or Submitted requests can be declined.'))
        
        # Update status
        self.status = 'declined'
        
        # Post message to chatter
        self.message_post(
            body=Markup(_('Purchase Request has been <strong>declined</strong>.')),
            subject=_('Purchase Request Declined: %s') % self.pr_number
        )
        return True

    def action_send_purchase_request_email(self):
        """Open mail composer to send Purchase Request information via email"""
        self.ensure_one()
        
        # Generate email body with all Purchase Request information
        email_body = self._generate_purchase_request_email_body()
        
        # Prepare context for mail compose wizard
        ctx = {
            'default_model': 'logilink.purchase.request.header',
            # Odoo 19+ requires default_res_ids (list) instead of default_res_id (single)
            'default_res_ids': [self.id],
            'default_composition_mode': 'comment',
            'default_subject': _('Purchase Request Information: %s') % self.pr_number,
            'default_body': email_body,
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'force_email': True,
            'form_view_ref': 'mail.email_compose_message_wizard_form',
            'clicked_on_full_composer': True,
        }
        
        # Send to Approver (Community), not Requested By.
        if self.approver_id and self.approver_id.partner_id:
            ctx["default_partner_ids"] = [(6, 0, [self.approver_id.partner_id.id])]
        elif self.approver_id and self.approver_id.email:
            ctx["default_email_to"] = self.approver_id.email
        
        return {
            'name': _('Send Purchase Request Information'),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def _generate_purchase_request_email_body(self):
        """Generate formatted email body with all Purchase Request information"""
        self.ensure_one()
        
        # Status color mapping - using solid colors with high contrast for dark/light mode compatibility
        status_colors = {
            'requested': {'bg': '#f5f5f5', 'text': '#424242', 'border': '#9e9e9e', 'badge_bg': '#757575', 'badge_text': '#ffffff'},
            'submitted': {'bg': '#e3f2fd', 'text': '#1565c0', 'border': '#1976d2', 'badge_bg': '#1976d2', 'badge_text': '#ffffff'},
            'approved': {'bg': '#e8f5e9', 'text': '#2e7d32', 'border': '#4caf50', 'badge_bg': '#4caf50', 'badge_text': '#ffffff'},
            'declined': {'bg': '#ffebee', 'text': '#c62828', 'border': '#f44336', 'badge_bg': '#f44336', 'badge_text': '#ffffff'},
        }
        status_info = status_colors.get(self.status, status_colors['requested'])
        
        # Start building the email body - using white background for light mode compatibility
        body_parts = []
        body_parts.append(f"<div style='font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif; max-width: 800px; margin: 0 auto; background-color: #ffffff; color: #212121;'>")
        
        # Header with solid background - dark text on light background
        body_parts.append(f"<div style='background-color: #2c3e50; padding: 30px; color: #ffffff;'>")
        body_parts.append(f"<h1 style='margin: 0; font-size: 28px; font-weight: 600; letter-spacing: -0.5px; color: #ffffff;'>Purchase Request</h1>")
        body_parts.append(f"<p style='margin: 8px 0 0 0; font-size: 16px; color: #e0e0e0;'>Request Information</p>")
        body_parts.append(f"</div>")
        
        # Status badge at the top
        status_label = Markup.escape(dict(self._fields['status'].selection).get(self.status, self.status))
        body_parts.append(f"<div style='padding: 20px 30px; background-color: {status_info['bg']}; border-left: 4px solid {status_info['border']}; margin: 20px 30px; border-radius: 4px;'>")
        body_parts.append(f"<span style='display: inline-block; padding: 8px 16px; background-color: {status_info['badge_bg']}; color: {status_info['badge_text']}; border-radius: 20px; font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;'>{status_label}</span>")
        body_parts.append(f"</div>")
        
        # Request Details Card
        body_parts.append(f"<div style='background-color: #f8f9fa; padding: 25px 30px; margin: 0 30px 20px 30px; border-radius: 8px; border: 1px solid #e0e0e0;'>")
        body_parts.append(f"<h2 style='color: #212121; margin: 0 0 20px 0; font-size: 20px; font-weight: 600;'>")
        body_parts.append(f"<span style='display: inline-block; width: 4px; height: 24px; background-color: #2c3e50; border-radius: 2px; margin-right: 12px; vertical-align: middle;'></span>")
        body_parts.append(f"Request Details</h2>")
        
        pr_number = Markup.escape(self.pr_number) if self.pr_number else 'N/A'
        date_requested = str(self.date_requested) if self.date_requested else 'N/A'
        date_needed = str(self.date_needed) if self.date_needed else 'N/A'
        dept_name = Markup.escape(self.department_id.name) if self.department_id and self.department_id.name else 'N/A'
        requested_by_name = (
            Markup.escape(self.requested_by_community_id.name)
            if self.requested_by_community_id and self.requested_by_community_id.name
            else 'N/A'
        )
        
        body_parts.append(f"<table style='width: 100%; border-collapse: collapse;'>")
        body_parts.append(f"<tr><td style='padding: 12px 0; font-weight: 600; color: #424242; width: 180px; border-bottom: 1px solid #e0e0e0;'>PR Number</td><td style='padding: 12px 0; color: #212121; border-bottom: 1px solid #e0e0e0;'><strong style='color: #212121;'>{pr_number}</strong></td></tr>")
        body_parts.append(f"<tr><td style='padding: 12px 0; font-weight: 600; color: #424242; border-bottom: 1px solid #e0e0e0;'>Date Requested</td><td style='padding: 12px 0; color: #212121; border-bottom: 1px solid #e0e0e0;'>{date_requested}</td></tr>")
        body_parts.append(f"<tr><td style='padding: 12px 0; font-weight: 600; color: #424242; border-bottom: 1px solid #e0e0e0;'>Date Needed</td><td style='padding: 12px 0; color: #212121; border-bottom: 1px solid #e0e0e0;'>{date_needed}</td></tr>")
        body_parts.append(f"<tr><td style='padding: 12px 0; font-weight: 600; color: #424242; border-bottom: 1px solid #e0e0e0;'>Department</td><td style='padding: 12px 0; color: #212121; border-bottom: 1px solid #e0e0e0;'>{dept_name}</td></tr>")
        body_parts.append(f"<tr><td style='padding: 12px 0; font-weight: 600; color: #424242; border-bottom: 1px solid #e0e0e0;'>Requested By</td><td style='padding: 12px 0; color: #212121; border-bottom: 1px solid #e0e0e0;'>{requested_by_name}</td></tr>")
        # PR now focuses on canvassing requested items (item + quantity + type). Costs/totals are handled on the Purchase Order.
        body_parts.append(f"</table>")
        body_parts.append(f"</div>")
        
        # Remarks Card
        if self.remarks:
            body_parts.append(f"<div style='background-color: #ffffff; padding: 25px 30px; margin: 0 30px 20px 30px; border-radius: 8px; border: 1px solid #e0e0e0; border-left: 4px solid #2196f3;'>")
            body_parts.append(f"<h2 style='color: #212121; margin: 0 0 15px 0; font-size: 18px; font-weight: 600;'>Remarks</h2>")
            remarks_text = self.remarks if isinstance(self.remarks, Markup) else (Markup.escape(self.remarks) if self.remarks else '')
            body_parts.append(f"<p style='margin: 0; color: #424242; line-height: 1.6;'>{remarks_text}</p>")
            body_parts.append(f"</div>")
        
        # Request Lines Card
        if self.line_ids:
            body_parts.append(f"<div style='background-color: #ffffff; padding: 25px 30px; margin: 0 30px 20px 30px; border-radius: 8px; border: 1px solid #e0e0e0;'>")
            body_parts.append(f"<h2 style='color: #212121; margin: 0 0 20px 0; font-size: 20px; font-weight: 600;'>")
            body_parts.append(f"<span style='display: inline-block; width: 4px; height: 24px; background-color: #2c3e50; border-radius: 2px; margin-right: 12px; vertical-align: middle;'></span>")
            body_parts.append(f"Requested Items</h2>")
            
            body_parts.append(f"<table style='width: 100%; border-collapse: collapse; margin-bottom: 15px; border: 1px solid #e0e0e0;'>")
            body_parts.append(f"<thead>")
            body_parts.append(f"<tr style='background-color: #2c3e50;'>")
            body_parts.append(f"<th style='padding: 14px; text-align: left; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #ffffff; border: 1px solid #1a252f;'>Item Description</th>")
            body_parts.append(f"<th style='padding: 14px; text-align: center; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #ffffff; border: 1px solid #1a252f;'>Quantity</th>")
            body_parts.append(f"<th style='padding: 14px; text-align: center; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #ffffff; border: 1px solid #1a252f;'>Item Type</th>")
            body_parts.append(f"</tr>")
            body_parts.append(f"</thead>")
            body_parts.append(f"<tbody>")
            
            for idx, line in enumerate(self.line_ids):
                row_bg = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
                item_desc = Markup.escape(line.item_description) if line.item_description else 'N/A'
                body_parts.append(f"<tr style='background-color: {row_bg};'>")
                body_parts.append(f"<td style='padding: 14px; border-bottom: 1px solid #e0e0e0; color: #212121; border-left: 1px solid #e0e0e0;'>{item_desc}</td>")
                body_parts.append(f"<td style='padding: 14px; text-align: center; border-bottom: 1px solid #e0e0e0; color: #424242; border-left: 1px solid #e0e0e0;'>{line.quantity_requested:,.2f}</td>")
                body_parts.append(f"<td style='padding: 14px; text-align: center; border-bottom: 1px solid #e0e0e0; color: #424242; border-left: 1px solid #e0e0e0;'>{dict(line._fields['item_type'].selection).get(line.item_type, line.item_type)}</td>")
                body_parts.append(f"</tr>")
            
            body_parts.append(f"</tbody>")
            body_parts.append(f"</table>")
            body_parts.append(f"</div>")
        else:
            body_parts.append(f"<div style='background-color: #fff9e6; padding: 20px 30px; margin: 0 30px 20px 30px; border-radius: 8px; border: 1px solid #e0e0e0; border-left: 4px solid #ff9800;'>")
            body_parts.append(f"<p style='margin: 0; color: #e65100; font-style: italic;'>No items have been added to this purchase request.</p>")
            body_parts.append(f"</div>")
        
        # Action Buttons (only show if status allows approval/decline)
        if self.status in ['requested', 'submitted']:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
            approve_url = f"{base_url}/purchase_request/{self.id}/approve"
            decline_url = f"{base_url}/purchase_request/{self.id}/decline"
            
            body_parts.append(f"<div style='padding: 30px; margin: 20px 30px; background-color: #f5f5f5; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center;'>")
            body_parts.append(f"<h3 style='color: #212121; margin: 0 0 20px 0; font-size: 18px; font-weight: 600;'>Take Action</h3>")
            body_parts.append(f"<div style='display: inline-block; margin: 0 10px;'>")
            body_parts.append(f"<a href='{approve_url}' style='display: inline-block; padding: 14px 32px; background-color: #4caf50; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px; border: none;'>✓ Approve</a>")
            body_parts.append(f"</div>")
            body_parts.append(f"<div style='display: inline-block; margin: 0 10px;'>")
            body_parts.append(f"<a href='{decline_url}' style='display: inline-block; padding: 14px 32px; background-color: #f44336; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px; border: none;'>✗ Decline</a>")
            body_parts.append(f"</div>")
            body_parts.append(f"<p style='margin: 15px 0 0 0; color: #757575; font-size: 13px;'>Click a button above to approve or decline this request. You can add a message when you click.</p>")
            body_parts.append(f"</div>")
        
        # Footer
        body_parts.append(f"<div style='padding: 20px 30px; text-align: center; color: #757575; font-size: 12px; border-top: 1px solid #e0e0e0; margin-top: 30px; background-color: #fafafa;'>")
        body_parts.append(f"<p style='margin: 0; color: #757575;'>This email was automatically generated from the Purchase Request system.</p>")
        body_parts.append(f"</div>")
        body_parts.append(f"</div>")
        
        return Markup(''.join(body_parts))


class LogilinkPurchaseRequestLine(models.Model):
    _name = "logilink.purchase.request.line"
    _description = "Purchase Request Line"
    _order = "pr_id, id"
    _rec_name = "item_description"

    pr_id = fields.Many2one("logilink.purchase.request.header", string="Purchase Request", required=True, ondelete="cascade", help="Purchase Request this line belongs to")
    item_description = fields.Text("Item Description", required=True, help="Description of the item requested")
    quantity_requested = fields.Float("Quantity Requested", required=True, default=1.0, help="Quantity of items requested")
    line_summary = fields.Char(
        string="Summary",
        compute="_compute_line_summary",
        help="Human-readable summary of this request line.",
    )
    po_line_ids = fields.One2many(
        "logilink.purchase.order.line",
        "pr_line_id",
        string="PO Lines",
        help="Purchase Order Lines created from this request line.",
    )
    ordered_qty = fields.Float(
        string="Ordered Quantity",
        compute="_compute_ordered_quantities",
        store=True,
        readonly=True,
        help="Sum of quantities ordered on related PO lines (excluding cancelled POs).",
    )
    remaining_qty = fields.Float(
        string="Remaining Quantity",
        compute="_compute_ordered_quantities",
        store=True,
        readonly=True,
        help="Requested quantity minus ordered quantity.",
    )
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

    @api.depends("item_description", "quantity_requested", "item_type")
    def _compute_line_summary(self):
        item_type_map = dict(self._fields["item_type"].selection)
        for rec in self:
            desc = (rec.item_description or "").strip() or _("(No Description)")
            type_label = item_type_map.get(rec.item_type, rec.item_type or "")
            qty = rec.quantity_requested or 0.0
            rec.line_summary = _(
                "%(desc)s | Qty: %(qty).2f | Type: %(type)s"
            ) % {
                "desc": desc,
                "qty": qty,
                "type": type_label,
            }

    @api.depends("quantity_requested", "po_line_ids.quantity_ordered", "po_line_ids.po_id.status")
    def _compute_ordered_quantities(self):
        for rec in self:
            relevant_po_lines = rec.po_line_ids.filtered(lambda l: l.po_id and l.po_id.status != "declined")
            ordered = sum(relevant_po_lines.mapped("quantity_ordered") or [0.0])
            rec.ordered_qty = ordered
            rec.remaining_qty = (rec.quantity_requested or 0.0) - ordered

    def name_get(self):
        """Make PR lines easy to identify when selecting them (e.g., from PO lines)."""
        res = []
        item_type_map = dict(self._fields["item_type"].selection)
        for rec in self:
            desc = (rec.item_description or "").strip() or _("(No Description)")
            type_label = item_type_map.get(rec.item_type, rec.item_type or "")
            qty = rec.quantity_requested or 0.0

            name = _(
                "%(desc)s | Qty: %(qty).2f | Type: %(type)s"
            ) % {
                "desc": desc,
                "qty": qty,
                "type": type_label,
            }
            res.append((rec.id, name))
        return res

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Allow searching PR lines by description or PR number."""
        args = list(args or [])
        if name:
            domain = [
                "|",
                ("item_description", operator, name),
                ("pr_id.pr_number", operator, name),
            ]
            args = domain + args
        recs = self.search(args, limit=limit)
        return recs.name_get()
