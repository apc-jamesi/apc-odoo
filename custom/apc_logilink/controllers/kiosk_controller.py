# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class KioskController(http.Controller):

    @http.route('/logilink/kiosk', type='http', auth='user', csrf=False)
    def kiosk_mode(self, **kwargs):
        """Kiosk mode interface for barcode scanning - NO WEBSITE MODULE"""
        return request.render('apc_logilink.kiosk_template', {})

    @http.route('/logilink/kiosk/scan', type='json', auth='user', methods=['POST'], csrf=False)
    def kiosk_scan(self, scan_value=None, **kwargs):
        """AJAX endpoint for barcode scanner input"""
        try:
            if not scan_value:
                return {
                    'success': False,
                    'message': 'No scan value provided',
                }
            # Try to find asset by asset_code
            asset = request.env['logilink.asset'].sudo().search([
                ('asset_code', '=', scan_value),
                ('active', '=', True)
            ], limit=1)
            
            if asset:
                request.session['kiosk_asset_id'] = asset.id
                request.session['kiosk_asset_name'] = asset.display_name
                
                # Get borrower information
                borrower_info = ""
                if asset.is_currently_borrowed and asset.current_borrower_id:
                    borrower_info = f"Currently borrowed by: {asset.current_borrower_id.name} (ID: {asset.current_borrower_id.id_number})"
                elif asset.last_borrower_id:
                    borrower_info = f"Last borrower: {asset.last_borrower_id.name} (ID: {asset.last_borrower_id.id_number})"
                    if asset.last_borrowed_date:
                        borrower_info += f" on {asset.last_borrowed_date.strftime('%Y-%m-%d')}"
                
                # Check if asset can be borrowed
                can_borrow = asset.status == 'working' and not asset.is_currently_borrowed
                borrow_reason = ""
                if asset.status != 'working':
                    status_label = dict(asset._fields['status'].selection).get(asset.status, asset.status)
                    borrow_reason = f"Asset status is '{status_label}'. Only assets with status 'Working' can be borrowed."
                elif asset.is_currently_borrowed:
                    borrow_reason = "Asset is currently borrowed by another person."
                
                return {
                    'success': True,
                    'type': 'asset',
                    'name': asset.display_name,
                    'message': f"Asset Detected: {asset.display_name}",
                    'borrower_info': borrower_info,
                    'is_currently_borrowed': asset.is_currently_borrowed,
                    'asset_status': asset.status,
                    'can_borrow': can_borrow,
                    'borrow_reason': borrow_reason,
                }
            
            # Try to find community member by id_number
            community = request.env['logilink.community'].sudo().search([
                ('id_number', '=', scan_value),
                ('active', '=', True)
            ], limit=1)
            
            if community:
                request.session['kiosk_community_id'] = community.id
                request.session['kiosk_community_name'] = community.name
                
                # Check if asset is already in session
                asset_id = request.session.get('kiosk_asset_id', False)
                if asset_id:
                    # Create request automatically
                    asset_obj = request.env['logilink.asset'].sudo().browse(asset_id)
                    try:
                        request_record = request.env['logilink.request'].sudo().create({
                            'asset_id': asset_id,
                            'community_id': community.id,
                            'request_type': 'borrow',
                            'state': 'pending',
                            'notes': f"Created via Kiosk Mode - Asset: {asset_obj.asset_code}, Community: {community.id_number}",
                        })
                        
                        # Clear session
                        request.session.pop('kiosk_asset_id', None)
                        request.session.pop('kiosk_asset_name', None)
                        request.session.pop('kiosk_community_id', None)
                        request.session.pop('kiosk_community_name', None)
                        
                        return {
                            'success': True,
                            'type': 'community',
                            'name': community.name,
                            'message': f"Borrower Detected: {community.name}",
                            'request_created': True,
                            'request_uuid': request_record.uuid,
                        }
                    except Exception as e:
                        _logger.error(f"Kiosk request creation error: {str(e)}")
                        return {
                            'success': True,
                            'type': 'community',
                            'name': community.name,
                            'message': f"Borrower Detected: {community.name} (Error creating request: {str(e)})",
                        }
                
                return {
                    'success': True,
                    'type': 'community',
                    'name': community.name,
                    'message': f"Borrower Detected: {community.name}",
                }
            
            # Not found
            return {
                'success': False,
                'message': f"Not found: {scan_value}. Please scan a valid Asset Code or ID Number.",
            }
            
        except Exception as e:
            _logger.error(f"Kiosk scan error: {str(e)}")
            return {
                'success': False,
                'message': f"Error processing scan: {str(e)}",
            }

    @http.route('/logilink/kiosk/create_request', type='json', auth='user', methods=['POST'], csrf=False)
    def kiosk_create_request(self, request_type=None, id_number=None, notes=None, **kwargs):
        """Create request from kiosk with type and notes"""
        try:
            asset_id = request.session.get('kiosk_asset_id', False)
            if not asset_id:
                return {
                    'success': False,
                    'message': 'No asset scanned. Please scan an asset first.',
                }
            
            asset_obj = request.env['logilink.asset'].sudo().browse(asset_id)
            if not asset_obj.exists():
                return {
                    'success': False,
                    'message': 'Asset not found.',
                }
            
            # Validate borrow request
            if request_type == 'borrow':
                # Check if asset status is 'working'
                if asset_obj.status != 'working':
                    status_label = dict(asset_obj._fields['status'].selection).get(asset_obj.status, asset_obj.status)
                    return {
                        'success': False,
                        'message': f"Cannot borrow asset. Asset status is '{status_label}'. Only assets with status 'Working' can be borrowed.",
                    }
                
                # Check if asset is currently borrowed
                if asset_obj.is_currently_borrowed:
                    borrower_name = asset_obj.current_borrower_id.name if asset_obj.current_borrower_id else 'Unknown'
                    return {
                        'success': False,
                        'message': f"Cannot borrow asset. Asset is currently borrowed by {borrower_name}.",
                    }
            
            community_id = False
            if request_type == 'borrow':
                if not id_number:
                    return {
                        'success': False,
                        'message': 'ID Number is required for borrow requests.',
                    }
                
                # Find community member
                community = request.env['logilink.community'].sudo().search([
                    ('id_number', '=', id_number),
                    ('active', '=', True)
                ], limit=1)
                
                if not community:
                    return {
                        'success': False,
                        'message': f'Community member with ID {id_number} not found.',
                    }
                community_id = community.id
            
            # Create request
            request_vals = {
                'asset_id': asset_id,
                'request_type': request_type or 'borrow',
                'state': 'pending',
                'notes': notes or f"Created via Kiosk Mode - Type: {request_type}, Asset: {asset_obj.asset_code}",
            }
            
            if community_id:
                request_vals['community_id'] = community_id
            
            request_record = request.env['logilink.request'].sudo().create(request_vals)
            
            # Clear session
            request.session.pop('kiosk_asset_id', None)
            request.session.pop('kiosk_asset_name', None)
            request.session.pop('kiosk_community_id', None)
            request.session.pop('kiosk_community_name', None)
            
            return {
                'success': True,
                'request_uuid': request_record.uuid,
                'message': f'Request created successfully: {request_record.uuid}',
            }
            
        except Exception as e:
            _logger.error(f"Kiosk create request error: {str(e)}")
            return {
                'success': False,
                'message': f'Error creating request: {str(e)}',
            }

    @http.route('/logilink/kiosk/clear', type='json', auth='user', methods=['POST'], csrf=False)
    def kiosk_clear(self, **kwargs):
        """Clear kiosk session"""
        request.session.pop('kiosk_asset_id', None)
        request.session.pop('kiosk_asset_name', None)
        request.session.pop('kiosk_community_id', None)
        request.session.pop('kiosk_community_name', None)
        return {'success': True}
