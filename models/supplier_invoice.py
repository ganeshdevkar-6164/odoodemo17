from odoo import models, fields, api

class SupplierInvoice(models.Model):
    _name = 'vighnahar_agro.supplier_invoice'
    _description = 'Supplier Invoice'
    
    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, index=True, default='New')
    description = fields.Text(string="Description")
    party_id = fields.Many2one('vighnahar_agro.party', string="Party/Supplier", required=True, domain=[('is_supplier', '=', True)])
    date = fields.Date(string="Date", default=fields.Date.today)
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    warehouse_id = fields.Many2one('vighnahar_agro.warehouse', string = "Warehouse", required=True)
    amount_due = fields.Float(string="Amount Due", compute='_compute_amount_due', store=True)
    paid_amount = fields.Float(string="Paid Amount", compute='_compute_total_paid', store=True)
    
    supplier_invoice_line_ids = fields.One2many('vighnahar_agro.supplier_invoice_line', 'invoice_id', string='Invoice Lines', ondelete='cascade')
    payment_ids = fields.One2many('vighnahar_agro.supplier_payment', 'invoice_id', string='Payments', ondelete='cascade')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('post', 'Posted'),
    ], default='draft', string="Invoice Status")
    
    payment_status = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ], compute='_compute_payment_status', string='Payment Status', default='pending', store=True)

    
    @api.depends('total_amount', 'paid_amount')
    def _compute_amount_due(self):
        for record in self:
            record.amount_due = record.total_amount - record.paid_amount

    @api.depends('total_amount', 'paid_amount')
    def _compute_payment_status(self):
        for record in self:
            # _logger.info(f"Computing payment status for {record.id}: total_amount = {record.total_amount}, paid_amount = {record.paid_amount}")
            if not record.supplier_invoice_line_ids or record.total_amount == 0:
                record.payment_status = 'pending'
            elif record.paid_amount == record.total_amount:
                record.payment_status = 'paid'
            elif record.paid_amount > 0.0:
                record.payment_status = 'partial'
            else:
                record.payment_status = 'pending'

    # Generate unique sequence number    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.supplier_invoice') or 'New'
        return super(SupplierInvoice, self).create(vals)

    # Calculate the total amount from invoice lines
    @api.depends('supplier_invoice_line_ids.total')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(line.total for line in record.supplier_invoice_line_ids)

    # Calculate total paid amount from related payments
    @api.depends('payment_ids.amount', 'payment_ids.state')
    def _compute_total_paid(self):
        for record in self:
            record.paid_amount = sum(payment.amount for payment in record.payment_ids if payment.state == 'paid')

    # Action to create payment (when invoice is not yet fully paid)
    def action_register_payment(self):
        self.ensure_one()  # Ensure we're working with a single invoice
        
        # Calculate the remaining amount to be paid
        remaining_amount = self.total_amount - self.paid_amount
        
        # Return the action to open the Supplier Payment form with pre-filled values
        return {
            'name': 'Register Payment',
            'type': 'ir.actions.act_window',
            'res_model': 'vighnahar_agro.supplier_payment',
            'view_mode': 'form',
            'view_id': self.env.ref('vighnahar_agro.view_supplier_payment_form').id,
            'target': 'new',  # Open the form in a modal
            'context': {
                'default_invoice_id': self.id,  # Set the default invoice
                'default_amount': remaining_amount,  # Set the default amount to be paid
                'default_state': 'draft',  # Set the payment state to draft by default
            },
        }

    
    # Action to confirm the invoice(nachiket Update)
    def action_confirm(self):
        # Step 1: Check if the warehouse exists in PhysicalInventory, if not create it
        physical_inventory = self.env['vighnahar_agro.physical_inventory'].search([('warehouse_id', '=', self.warehouse_id.id)], limit=1)

        if not physical_inventory:
            # If the warehouse doesn't exist in PhysicalInventory, create a new record
            physical_inventory = self.env['vighnahar_agro.physical_inventory'].create({
                'warehouse_id': self.warehouse_id.id,
            })
        
        # Step 2: Update or create InventoryLine records for each invoice line
        for line in self.supplier_invoice_line_ids:
            # Get or create the corresponding InventoryLine record
            inventory_line = self.env['vighnahar_agro.inventory_line'].search([
                ('physical_inventory_id', '=', physical_inventory.id),
                ('product_category_id', '=', line.product_category_id.id),
                ('product_id', '=', line.product_id.id),
                
            ], limit=1)

            if inventory_line:
                # If the record exists, add the new quantity to the existing quantity
                inventory_line.write({
                    'quantity': inventory_line.quantity + line.converted_quantity,  # Add the converted quantity
                    'uom_id': line.converted_uom_id.id,  # Update UOM if necessary
                })
            else:
                # If the record doesn't exist, create a new InventoryLine
                self.env['vighnahar_agro.inventory_line'].create({
                    'physical_inventory_id': physical_inventory.id,
                    'product_category_id': line.product_category_id.id,
                    'product_id': line.product_id.id,
                    'quantity': line.converted_quantity,
                    'uom_id': line.converted_uom_id.id,
                })
            
            

        # Step 3: Set the state of the invoice to 'post'
        self.state = 'post'
        

class SupplierInvoiceLine(models.Model):
    _name = 'vighnahar_agro.supplier_invoice_line'
    _description = 'Supplier Invoice Line'

    invoice_id = fields.Many2one('vighnahar_agro.supplier_invoice', string='Invoice', ondelete='cascade')
    uom_category_id = fields.Many2one('vighnahar_agro.uom_category', related='product_id.category_id', string='UOM Category')
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

    @api.depends('product_id')
    def _compute_available_product_categories(self):
        for line in self:
            product_ids = self.env['vighnahar_agro.product'].search([('can_be_purchased', '=', True)])
            category_ids = product_ids.mapped('product_category_id')
            line.available_product_category_ids = category_ids


class SupplierPayment(models.Model):
    _name = 'vighnahar_agro.supplier_payment'
    _description = 'Supplier Payment'
    
    name = fields.Char(string="Payment Reference", required=True, copy=False, readonly=True, index=True, default='New')
    payment_date = fields.Date(string='Payment Date', default=fields.Date.today)
    amount = fields.Float(string="Amount", required=True)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('cheque', 'Cheque'),
        ('online', 'Online')
    ], string="Payment Method", required=True, default='cash')
    invoice_id = fields.Many2one('vighnahar_agro.supplier_invoice', string='Supplier Invoice', required=True)
    state = fields.Selection([('draft', 'Draft'), ('paid', 'Paid')], string="Payment Status", default='draft')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.supplier_payment') or 'New'
        return super(SupplierPayment, self).create(vals)

    def action_pay(self):
        """Update the payment status to 'paid' and reflect the payment amount"""
        self.state = 'paid'
        self.invoice_id.payment_ids |= self  # Link payment to invoice
        # Optionally, update invoice total paid amount
        paid_amount = sum(payment.amount for payment in self.invoice_id.payment_ids if payment.state == 'paid')
        self.invoice_id.paid_amount = paid_amount
        