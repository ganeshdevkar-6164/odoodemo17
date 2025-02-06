from odoo import models, fields, api
from odoo.exceptions import UserError

class SalesOrder(models.Model):
    _name = 'sale.order.custom'
    _description = 'Sales Order Custom'

    name = fields.Char(string='Sales Order Number', required=True, copy=False, readonly=True, default='New')
    customer_id = fields.Many2one('customer.registration', string='Customer', required=True)
    order_date = fields.Datetime(string='Order Date', default=fields.Datetime.now)
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    state = fields.Selection([('draft', 'Draft'), ('sale_order', 'Sale Order'), ('cancelled', 'Cancelled')], default='draft', string='Status')

    order_line = fields.One2many('sale.order.line.custom', 'sale_order_id', string='Order Lines')
    
    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sales.order.custom.sequence')
        return super().create(vals)

    @api.depends('order_line')
    def _compute_total_amount(self):
        """Compute the total amount of the order based on the order lines."""
        for order in self:
            order.total_amount = sum(line.subtotal for line in order.order_line)

    def action_confirm(self):
        """Confirm the sales order and set the state to 'sale_order'."""
        self.ensure_one()
        if self.state not in ['draft']:
            raise UserError('You can only confirm an order that is in draft state.')
        self.write({'state': 'sale_order'})

    def action_cancel(self):
        """Cancel the sales order and set the state to 'cancelled'."""
        self.ensure_one()
        if self.state == 'sale_order':
            self.write({'state': 'cancelled'})
        else:
            raise UserError('Only sales orders in the "sale_order" state can be canceled.')

    def action_create_invoice(self):
        """Create an invoice from the sales order."""
        self.ensure_one()
        invoice = self.env['sale.invoice.custom'].create({
            'sale_order_id': self.id,
            'customer_id': self.customer_id.id,
            'total_amount': self.total_amount,
        })
        # Create invoice lines from sale order lines
        for line in self.order_line:
            self.env['invoice.sale.line.custom'].create({
                'invoice_order_id': invoice.id,
                'product_id': line.product_id.id,
                'product_qty': line.product_qty,
                'price_unit': line.price_unit,
                'subtotal': line.subtotal,
                'product_category_id': line.product_category_id.id,  # Ensure the product_category_id is assigned

            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'sale.invoice.custom',
            'res_id': invoice.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }

class SalesOrderLine(models.Model):
    _name = 'sale.order.line.custom'
    _description = 'Sales Order Line Custom'

    sale_order_id = fields.Many2one('sale.order.custom', string='Sale Order', required=True)
    product_category_id = fields.Many2one('custom.product.category', string="Product Category", required=True)
    product_id = fields.Many2one('custom.product', string='Product', required=True, domain="[('product_category_id','=',product_category_id)]")
    product_qty = fields.Float(string='Quantity', required=True)
    category_id = fields.Many2one('custom.uom.category', string="UOM Category", required=True,
                                  default=lambda self: self.env['custom.uom.category'].search([('name', '=', 'Weight')], limit=1))
    uom_id = fields.Many2one('custom.uom', related='product_id.uom_id', string='Unit of Measure', store="true", domain="[('category_id','=',category_id)]")
    price_unit = fields.Float(string='Unit Price', related='product_id.sales_price', required=True)
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('product_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_qty * line.price_unit


class SalesInvoice(models.Model):
    _name = 'sale.invoice.custom'
    _description = 'Sales Invoice Custom'

    name = fields.Char(string='Invoice Number', required=True, copy=False, readonly=True, default='New')
    sale_order_id = fields.Many2one('sale.order.custom', string='Sales Order', required=True)
    customer_id = fields.Many2one('customer.registration', string='Customer', related='sale_order_id.customer_id', readonly=True)
    invoice_date = fields.Datetime(string='Invoice Date', default=fields.Datetime.now)
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted'), ('cancelled', 'Cancelled')], default='draft', string='Status')
    
    order_line_ids = fields.One2many('invoice.sale.line.custom', 'invoice_order_id', string='Invoice Lines')
    
    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sales.invoice.custom.sequence')
        return super().create(vals)

    @api.depends('sale_order_id.order_line')
    def _compute_total_amount(self):
        """Compute the total amount for the invoice based on sales order lines."""
        for invoice in self:
            invoice.total_amount = sum(line.subtotal for line in invoice.sale_order_id.order_line)

    def action_post(self):
        """Post the invoice and set the state to 'posted'."""
        self.ensure_one()
        if self.state == 'draft':
            self.write({'state': 'posted'})

    def action_cancel(self):
        """Cancel the invoice."""
        self.ensure_one()
        if self.state == 'posted':
            self.write({'state': 'cancelled'})
    
    def action_create_payment(self):
        """Create a payment linked to the sales invoice."""
        self.ensure_one()
        payment = self.env['sale.payment.custom'].create({
            'invoice_id': self.id,
            'amount': self.total_amount,
            'state': 'draft',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment',
            'res_model': 'sale.payment.custom',
            'res_id': payment.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }


class InvoiceOrderLine(models.Model):
    _name = 'invoice.sale.line.custom'
    _description = 'Invoice sale Line Custom'

    invoice_order_id = fields.Many2one('sale.invoice.custom', string='Invoice ID', required=True)
    product_category_id = fields.Many2one('custom.product.category', string="Product Category", required=True)
    product_id = fields.Many2one('custom.product', string='Product', required=True, domain="[('product_category_id','=',product_category_id)]")    
    product_qty = fields.Float(string='Quantity', required=True)
    category_id = fields.Many2one('custom.uom.category', string="UOM Category", required=True,
                                  default=lambda self: self.env['custom.uom.category'].search([('name', '=', 'Weight')], limit=1))
    uom_id = fields.Many2one('custom.uom', related='product_id.uom_id', string='Unit of Measure', store="true", domain="[('category_id','=',category_id)]")
    price_unit = fields.Float(string='Unit Price', related='product_id.sales_price', required=True)
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('product_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_qty * line.price_unit


class SalesPayment(models.Model):
    _name = 'sale.payment.custom'
    _description = 'Sales Payment Custom'

    name = fields.Char(string='Payment Number', required=True, copy=False, readonly=True, default='New')
    invoice_id = fields.Many2one('sale.invoice.custom', string='Invoice', required=True)
    customer_id = fields.Many2one('customer.registration', string='Customer', related='invoice_id.customer_id', readonly=True)
    payment_date = fields.Date(string='Payment Date', default=fields.Date.today())
    amount = fields.Float(string='Amount', required=True)
    state = fields.Selection([('draft', 'Draft'), ('paid', 'Paid')], default='draft', string='Status')

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sales.payment.custom.sequence')
        return super().create(vals)

    def action_post(self):
        """Mark the payment as 'paid'."""
        self.ensure_one()
        if self.state == 'draft':
            self.write({'state': 'paid'})
