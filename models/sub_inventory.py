from odoo import models, fields

class SubInventory(models.Model):
    _name = 'sub.inventory'
    _description = 'Physical Inventory for Products'
    _rec_name='product_id'

    # New fields for warehouse, product category, UOM, date
    warehouse_id = fields.Many2one('sub.inventory.warehouse', string='Warehouse Location', required=True)
    product_id = fields.Many2one('custom.product', string='Product', required=True)
    product_category_id = fields.Many2one('custom.product.category', string='Product Category', related='product_id.product_category_id', store=True)
    uom_id = fields.Many2one('custom.uom', string='UOM', related='product_id.uom_id', store=True)
    quantity = fields.Float('Quantity')
