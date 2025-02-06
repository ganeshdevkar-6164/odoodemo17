from odoo import models, fields, api

class CustomPhysicalInventory(models.Model):
    _name = 'custom.physical.inventory'
    _description = 'Physical Inventory for Products'

    # New fields for warehouse, product category, UOM, date
    wh_loc_id = fields.Many2one('custom.inventory.warehouse', string='Warehouse Location', required=True)
    product_id = fields.Many2one('custom.product', string='Product', required=True)
    product_category_id = fields.Many2one('custom.product.category', string='Product Category', related='product_id.product_category_id', store=True)
    uom_id = fields.Many2one('custom.uom', string='UOM', related='product_id.uom_id', store=True)
    quantity = fields.Float('Quantity')

    @api.model
    def create(self, vals):
        """Override create to update product quantity based on physical inventory"""
        record = super(CustomPhysicalInventory, self).create(vals)
        # Update the product's quantity based on physical inventory quantity
        record._update_product_quantity()
        return record

    def write(self, vals):
        """Override write to update product quantity based on physical inventory quantity"""
        res = super(CustomPhysicalInventory, self).write(vals)
        # Update the product's quantity based on physical inventory quantity
        self._update_product_quantity()
        return res

    def _update_product_quantity(self):
        """Helper method to update the product's quantity"""
        for inventory in self:
            # Get the corresponding product and update its quantity
            product = inventory.product_id
            product._compute_total_quantity()  # Recompute the total quantity for the product