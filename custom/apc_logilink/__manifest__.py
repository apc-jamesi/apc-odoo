# -*- coding: utf-8 -*-
{
    "name": "Logilink - Asset Registry System",
    "summary": "Comprehensive asset registry and management system for Asia Pacific College",
    "description": """
        Logilink - Asset Registry System
        =================================
        
        A specialized asset management application designed for Asia Pacific College
        to track and manage all institutional assets including:
        
        * Asset Registration and Tracking
        * Asset Code and Serial Number Management
        * Purchase Order and Supplier Tracking
        * Warranty Expiration Monitoring
        * Department and Area Assignment
        * Asset Receipt and Assignment Tracking
        
        This module provides a centralized platform for managing all institutional assets
        within the Asia Pacific College ecosystem, ensuring efficient tracking, maintenance,
        and accountability of equipment, devices, and other assets.
    """,
    "version": "19.0.1.0.0",
    "category": "Inventory/Assets",
    "author": "Asia Pacific College",
    "website": "https://www.apc.edu.ph",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web"],
    "data": [
        "views/department_views.xml",
        "views/asset_views.xml",
        "views/asset_borrowing_views.xml",
        "views/purchase_request_views.xml",
        "views/purchase_order_views.xml",
        "views/goods_receipt_views.xml",
        "views/supplier_invoice_views.xml",
        "views/payment_views.xml",
        "views/logilink_menu.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": True,
}
