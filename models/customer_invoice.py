from odoo import models, fields, api, _ 
from odoo.exceptions import UserError, ValidationError


class CustomerInvoce(models.Model):
    _name = 'vighnahar_agro.customer_invoice'
    _description = 'Customer Invoice'
    
    name = fields.Char(string="Reference", default='New')
    description = fields.Text(string="Description")
    party_id = fields.Many2one('vighnahar_agro.party', string="Party", required=True,domain=[('is_customer', '=', True)])
    date = fields.Date(string = "Date", default=fields.Date.today)
    invoice_type = fields.Selection([('standard','Standard'),('credit','Credit Memo'),('debit','Debit Memo'),('prepayment', 'Pre Payment')], string='Invoice Type', default = 'standard')
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    
    
    # Customer Invoice Line
    customer_invoice_line_ids = fields.One2many('vighnahar_agro.customer_invoice_line', 'customer_invoice_id', string='Invoice Lines')
    
    
    
    # generate unique sequence number
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.customer_invoice')
                  
        return super().create(vals_list)
    
    
    
    # calculate the total amount
    @api.depends('customer_invoice_line_ids.total')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(line.total for line in record.customer_invoice_line_ids)
    
    
    
    
    
class CustomerInvoiceLine(models.Model):
    _name = 'vighnahar_agro.customer_invoice_line'
    _description = 'Customer Invoice Line'

    customer_invoice_id = fields.Many2one('vighnahar_agro.customer_invoice', string='Invoice')
    uom_category_id = fields.Many2one('vighnahar_agro.uom_category',related = 'product_id.category_id' , string='UOM Category')
    product_category_id = fields.Many2one('vighnahar_agro.product_category', string='Product Category', domain="[('id', 'in', available_product_category_ids)]")
    product_id = fields.Many2one('vighnahar_agro.product', string='Product', domain="[('product_category_id', '=', product_category_id)]")
    quantity = fields.Float(string='Quantity', digits=(16, 4))
    uom_id = fields.Many2one('vighnahar_agro.uom', string='UOM', domain="[('category_id', '=', uom_category_id)]")
    price = fields.Float(string='Unit Price', related='product_id.cost_price', store=True)
    total = fields.Float(string='Total Price', compute='_compute_total', store=True)
    converted_quantity = fields.Float(string='Converted Quantity', digits=(16, 4), compute='_compute_converted_quantity', store=True)
    converted_uom_id = fields.Many2one('vighnahar_agro.uom', string='Converted UOM', compute='_compute_converted_quantity', store=True)
    available_product_category_ids = fields.Many2many('vighnahar_agro.product_category', compute='_compute_available_product_categories')
    
    @api.depends('quantity', 'uom_id', 'uom_category_id')
    def _compute_converted_quantity(self):
        for line in self:
            if line.uom_category_id:
                base_uom = self.env['vighnahar_agro.uom'].search([('category_id', '=', line.uom_category_id.id), ('factor', '=', 1)], limit=1)
                if line.uom_id and base_uom:
                    line.converted_quantity = line.quantity * line.uom_id.factor / base_uom.factor
                    line.converted_uom_id = base_uom.id
                else:
                    line.converted_quantity = line.quantity
                    line.converted_uom_id = base_uom.id if base_uom else False
            else:
                line.converted_quantity = line.quantity
                line.converted_uom_id = False


    @api.depends('converted_quantity', 'price')
    def _compute_total(self):
        for line in self:
            line.total = line.converted_quantity * line.price
    
    
    @api.depends('converted_quantity', 'price')
    def _compute_total(self):
        for line in self:
            line.total = line.converted_quantity * line.price

    
            
    @api.depends('product_id')
    def _compute_available_product_categories(self):
        for line in self:
            product_ids = self.env['vighnahar_agro.product'].search([('can_be_sold', '=', True)])
            category_ids = product_ids.mapped('product_category_id')
            line.available_product_category_ids = category_ids
    