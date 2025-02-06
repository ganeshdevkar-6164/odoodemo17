from odoo import models, fields, api

class CustomProductCategory(models.Model):
    _name = 'custom.product.category'
    _description = 'Custom Product Category'

    name = fields.Char(string="Category Name", required=True)
    code = fields.Char(string="Category Code", required=True)
    description = fields.Text(string="Description")


class CustomProduct(models.Model):
    _name = 'custom.product'
    _description = 'Custom Product'

    name = fields.Char(string="Product Name", required=True)
    product_category_id = fields.Many2one('custom.product.category', string="Category", required=True)
    grade = fields.Char(string="Grade")  # Add Grade Field
    wh_loc_id = fields.Many2one('custom.inventory.warehouse', string="Warehouse")
    # quantity = fields.Float(string="On-hand Quantity", default=0.0, readonly=False)  # Allow changes via stock moves
    sales_price = fields.Float(string="Sales Price", default=0.0)
    cost_price = fields.Float(string="Cost Price", default=0.0)
    image = fields.Binary('Product Image')
    category_id = fields.Many2one('custom.uom.category', string="UOM Category", required=True,
                                  default=lambda self: self.env['custom.uom.category'].search([('name', '=', 'Weight')], limit=1))  # Link to Custom UOM categories
    uom_id = fields.Many2one('custom.uom', string='Unit of Measure', store="true",
                             default=lambda self: self.env['custom.uom'].search([('name', '=', 'kg')], limit=1))
    description = fields.Text(string="Product Description")  # This field will store product description

    quantity = fields.Float(string="On-hand Quantity", default=0.0, readonly=True)

    # Relating the physical inventory records to the product
    physical_inventory_ids = fields.One2many(
        'custom.physical.inventory', 'product_id', string='Physical Inventory Records'
    )

    @api.depends('physical_inventory_ids.quantity')
    def _compute_total_quantity(self):
        """Compute the total quantity of the product across all warehouses."""
        for product in self:
            # Sum the quantities from all related physical inventory records
            total_qty = sum(inventory.quantity for inventory in product.physical_inventory_ids)
            product.quantity = total_qty