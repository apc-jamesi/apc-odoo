# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import uuid

class LogilinkRequest(models.Model):
    _name = "logilink.request"
    _description = "Asset Request (Kiosk Buffer)"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"

    uuid = fields.Char("UUID", required=True, default=lambda self: str(uuid.uuid4()), readonly=True, copy=False, index=True, help="Unique identifier for the request")
    asset_id = fields.Many2one("logilink.asset", string="Asset", required=True, help="Asset being requested")
    community_id = fields.Many2one("logilink.community", string="Community Member", required=False, help="Community member making the request (required for borrow, optional for return/repair)")
    request_type = fields.Selection([
        ('borrow', 'Borrow'),
        ('return', 'Return'),
        ('repair', 'Repair'),
    ], string="Request Type", required=True, default='borrow', help="Type of request")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string="State", default='draft', required=True, tracking=True, help="Current state of the request")
    notes = fields.Text("Notes", help="Additional notes or remarks")
    approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True, help="User who approved the request")
    approved_date = fields.Datetime("Approved Date", readonly=True, help="Date and time when the request was approved")
    borrowing_id = fields.Many2one("logilink.asset.borrowing", string="Borrowing Record", readonly=True, help="Created borrowing record after approval")

    _sql_constraints = [
        ("uuid_unique", "unique(uuid)", "UUID must be unique."),
    ]

    @api.constrains("asset_id", "request_type", "community_id")
    def _check_asset_status(self):
        """Ensure asset cannot be borrowed if status is not 'working' or if currently borrowed"""
        for rec in self:
            if rec.request_type == 'borrow':
                if not rec.community_id:
                    raise ValidationError(_("Community Member is required for borrow requests."))
                if rec.asset_id and rec.state in ('draft', 'pending'):
                    # Check asset status
                    if rec.asset_id.status != 'working':
                        status_label = dict(rec.asset_id._fields['status'].selection).get(rec.asset_id.status, rec.asset_id.status)
                        raise ValidationError(
                            _("Cannot borrow asset '%s' because its status is '%s'. Only assets with status 'Working' can be borrowed.")
                            % (rec.asset_id.display_name, status_label)
                        )
                    # Check if asset is currently borrowed
                    if rec.asset_id.is_currently_borrowed:
                        borrower_name = rec.asset_id.current_borrower_id.name if rec.asset_id.current_borrower_id else 'Unknown'
                        raise ValidationError(
                            _("Cannot borrow asset '%s' because it is currently borrowed by %s.")
                            % (rec.asset_id.display_name, borrower_name)
                        )

    def action_approve(self):
        """Approve the request and create Asset Borrowing record"""
        for rec in self:
            if rec.state != 'pending':
                raise ValidationError(_("Only pending requests can be approved."))
            
            if rec.request_type == 'borrow':
                # Create Asset Borrowing record
                borrowing = self.env['logilink.asset.borrowing'].create({
                    'asset_id': rec.asset_id.id,
                    'community_id': rec.community_id.id,
                    'borrowed_date': fields.Date.today(),
                    'status': 'borrowed',
                    'notes': rec.notes or f"Approved via Kiosk Request: {rec.uuid}",
                })
                
                rec.borrowing_id = borrowing.id
                
                # Post message to Asset Registry Chatter
                rec.asset_id.message_post(
                    body=f"Handshake Complete: Asset assigned to {rec.community_id.name} (ID: {rec.community_id.id_number}) via Kiosk Request {rec.uuid}.",
                    subject="Asset Assigned via Kiosk"
                )
                
                # Note: Asset status remains 'working' - borrowing is tracked via Asset Borrowing records
                
            elif rec.request_type == 'return':
                # Find active borrowing record for this asset
                active_borrowing = self.env['logilink.asset.borrowing'].search([
                    ('asset_id', '=', rec.asset_id.id),
                    ('status', '=', 'borrowed'),
                ], order='borrowed_date desc', limit=1)
                
                if active_borrowing:
                    active_borrowing.write({
                        'status': 'returned',
                        'actual_return_date': fields.Date.today(),
                        'notes': (active_borrowing.notes or '') + f"\nReturned via Kiosk Request {rec.uuid}. {rec.notes or ''}",
                    })
                    rec.borrowing_id = active_borrowing.id
                    
                    # Post message to Asset Registry Chatter
                    rec.asset_id.message_post(
                        body=f"Asset returned via Kiosk Request {rec.uuid}. {rec.notes or ''}",
                        subject="Asset Returned via Kiosk"
                    )
                else:
                    # No active borrowing found, just log the return request
                    rec.asset_id.message_post(
                        body=f"Return request processed via Kiosk Request {rec.uuid}. {rec.notes or ''}",
                        subject="Asset Return Request via Kiosk"
                    )
                    
            elif rec.request_type == 'repair':
                # Update asset status to 'under_maintenance'
                rec.asset_id.write({
                    'status': 'under_maintenance',
                })
                
                # Post message to Asset Registry Chatter
                rec.asset_id.message_post(
                    body=f"Asset marked for repair via Kiosk Request {rec.uuid}. {rec.notes or ''}",
                    subject="Asset Repair Request via Kiosk"
                )
            
            rec.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            
            rec.message_post(body=_("Request approved by %s") % self.env.user.name)
        
        return True

    def action_reject(self):
        """Reject the request"""
        for rec in self:
            if rec.state != 'pending':
                raise ValidationError(_("Only pending requests can be rejected."))
            
            rec.write({
                'state': 'rejected',
            })
            
            rec.message_post(body=_("Request rejected by %s") % self.env.user.name)
        
        return True

    def action_reset_to_draft(self):
        """Reset request to draft state"""
        for rec in self:
            rec.write({
                'state': 'draft',
                'approved_by_id': False,
                'approved_date': False,
            })
        
        return True
