# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PurchaseRequestController(http.Controller):

    @http.route('/purchase_request/<int:pr_id>/approve', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def approve_request(self, pr_id, message='', **kwargs):
        """Handle approve action from email button"""
        try:
            pr = request.env['logilink.purchase.request.header'].sudo().browse(pr_id)
            if not pr.exists():
                return request.render('apc_logilink.pr_action_error', {
                    'error': 'Purchase Request not found'
                })
            
            # If POST, process the approval
            if request.httprequest.method == 'POST':
                message = request.params.get('message', '').strip() or kwargs.get('message', '').strip()
                pr.action_approve_with_message(message)
                return request.render('apc_logilink.pr_action_success', {
                    'pr': pr,
                    'action': 'approved',
                    'message': message
                })
            
            # If GET, show the form
            return request.render('apc_logilink.pr_action_form', {
                'pr': pr,
                'action': 'approve',
                'action_label': 'Approve',
                'action_url': f'/purchase_request/{pr_id}/approve',
                'button_color': '#27ae60',
                'button_bg': '#e8f5e9'
            })
        except Exception as e:
            _logger.error(f"Error approving purchase request {pr_id}: {str(e)}")
            return request.render('apc_logilink.pr_action_error', {
                'error': str(e)
            })

    @http.route('/purchase_request/<int:pr_id>/decline', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def decline_request(self, pr_id, message='', **kwargs):
        """Handle decline action from email button"""
        try:
            pr = request.env['logilink.purchase.request.header'].sudo().browse(pr_id)
            if not pr.exists():
                return request.render('apc_logilink.pr_action_error', {
                    'error': 'Purchase Request not found'
                })
            
            # If POST, process the decline
            if request.httprequest.method == 'POST':
                message = request.params.get('message', '').strip() or kwargs.get('message', '').strip()
                pr.action_decline_with_message(message)
                return request.render('apc_logilink.pr_action_success', {
                    'pr': pr,
                    'action': 'declined',
                    'message': message
                })
            
            # If GET, show the form
            return request.render('apc_logilink.pr_action_form', {
                'pr': pr,
                'action': 'decline',
                'action_label': 'Decline',
                'action_url': f'/purchase_request/{pr_id}/decline',
                'button_color': '#e74c3c',
                'button_bg': '#ffebee'
            })
        except Exception as e:
            _logger.error(f"Error declining purchase request {pr_id}: {str(e)}")
            return request.render('apc_logilink.pr_action_error', {
                'error': str(e)
            })
