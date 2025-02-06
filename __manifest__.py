{
    'name': 'Agro Company',
    'version': '1.0',
    'category': 'Services',
    'summary': 'A simple Agro Company system',
    'author': 'Ganesh Devkar',
    'depends': ['base','web','mail'],
    'data': [
        
        'views/menu_views.xml',
        'views/supplier_views.xml',
        'views/customer_views.xml',
        'views/custom_product_views.xml',
        'views/custom_resource_views.xml',
        'views/custom_uom_views.xml',
        'views/inventory_stock_loc_views.xml',
        'views/purchase_order_views.xml',
        'views/sales_order_views.xml',
        'views/custom_inventory_views.xml',
        'views/inventory_transfer_views.xml',
        'views/dehusking_mfg_views.xml',
        'views/mfg_cutting_views.xml',
        'data/custom_inventory_sequences.xml',
        'security/ir.model.access.csv',  # Add the access control file here
                
    ],
    'assets': {
        'web.assets_backend': [
            'agro_company/static/src/css/custom_styles.css',
        ],
    },
    'installable': True,
    'application': True,
    'sequence': 1,
}