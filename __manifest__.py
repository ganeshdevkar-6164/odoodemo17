{
    'name': 'Vighnahar Agro',
    'version': '1.2',
    'category': 'Inventory/Purchase',
    'summary': 'Vighnahar Agro',
    'depends': ['base', 'web', 'mail','website_google_map','base_geolocalize'],
    'data': [
         'views/menu_items.xml',
         'security/ir.model.access.csv',
         'views/product_views.xml',
         'views/supplier_invoice_views.xml',
         'views/customer_invoice_views.xml',
         'views/uom_views.xml',
         'views/party_views.xml',
        # 'views/credit_memo_views.xml'
        # 'data/sequence.xml',
        
    ],
    'assets': {
        'web.assets_backend': [
            'vighnahar_agro/static/src/css/custom_styles.css',
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css',
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css',
        ],
     
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}