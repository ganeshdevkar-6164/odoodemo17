from datetime import datetime # type: ignore
from odoo import models, fields, api
from odoo.exceptions import UserError


# Purchase Order Custom Model
class PurchaseOrder(models.Model):
    _name = 'purchase.order.custom'
    _description = 'Purchase Order Custom'

    name = fields.Char(string='Purchase Order Number', required=True, copy=False, readonly=True, default='New')
    supplier_id = fields.Many2one('supplier.registration', string='Supplier', required=True)
    wh_loc_id = fields.Many2one('custom.inventory.warehouse', string='Warehouse location', required=True)
    date_order = fields.Datetime(string='Order Date', default=fields.Datetime.now)
    remaining_loan = fields.Float(string='Remaining Loan', compute='_compute_remaining_loan', store=True)
    deduct_loan_amount = fields.Boolean(string='Deduct Loan Amount', default=False)
    amount_total = fields.Float(string='Total Amount', compute='_compute_amount_total', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('purchase_order', 'Purchase Order'),
        ('cancelled', 'Cancelled')
    ], default='draft', string='Status')

    order_line = fields.One2many('purchase.order.line.custom', 'purchase_order_id', string='Order Lines')

    land_ids = fields.Many2many('supplier.land', string='Land Details')
    loan_ids = fields.Many2many('custom.resource.share', string='Loan Details', compute='_compute_loan_ids')
    
    loan_found = fields.Boolean(string="Loan Found", compute="_compute_loan_found", store=False)

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.order.custom.sequence')
        return super().create(vals)
    
    @api.depends('supplier_id')
    def _compute_loan_found(self):
        for record in self:
            loan_records = self.env['custom.resource.share'].search([
                ('state', '=', 'loan'),
                ('supplier_id', '=', record.supplier_id.id)
            ])
            record.loan_found = bool(loan_records)
            
    def action_loan_details(self):
        """Action to show loan details filtered by state='loan' and supplier."""
        self.ensure_one()

        # Search for loan records for the selected supplier
        loan_records = self.env['custom.resource.share'].search([
            ('state', '=', 'loan'),
            ('supplier_id', '=', self.supplier_id.id)
        ])

        if loan_records:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Loan Details',
                'res_model': 'custom.resource.share',  # Replace with your model if different
                'view_mode': 'tree,form',
                'domain': [
                    ('state', '=', 'loan'),
                    ('supplier_id', '=', self.supplier_id.id)
                ],
                'target': 'current',
            }
        else:
            # No loan records found
            return {
                'type': 'ir.actions.act_window',
                'name': 'Loan Details',
                'res_model': 'custom.resource.share',
                'view_mode': 'tree,form',
                'target': 'current',
                'context': {
                    'loan_found': False  # Set flag to False
                }
            }


    @api.depends('supplier_id')
    def _compute_loan_ids(self):
        """Compute the loans related to the selected supplier."""
        for order in self:
            order.loan_ids = self.env['custom.resource.share'].search([('supplier_id', '=', order.supplier_id.id)])

    @api.depends('loan_ids')
    def _compute_remaining_loan(self):
        """Compute the remaining loan for the supplier."""
        for order in self:
            remaining_loan_amount = sum(loan.amount for loan in order.loan_ids if loan.state == 'loan')
            order.remaining_loan = remaining_loan_amount

    @api.depends('order_line', 'loan_ids', 'deduct_loan_amount')
    def _compute_amount_total(self):
        """Compute the total amount of the order, factoring in loans and deduct_loan_amount."""
        for order in self:
            product_line_amount = sum(line.subtotal for line in order.order_line)
            total_loan_amount = sum(loan.amount for loan in order.loan_ids if loan.state == 'loan')

            if order.deduct_loan_amount:
                order.amount_total = product_line_amount - total_loan_amount
            else:
                order.amount_total = product_line_amount

    def action_confirm(self):
        """Confirm the purchase order and set the state to 'purchase_order'."""
        self.ensure_one()
        if self.state not in ['draft']:
            raise UserError('You can only confirm an order that is in draft state.')
        self.write({'state': 'purchase_order'})
        
    def action_cancel(self):
        """Cancel the purchase order and set the state to 'cancelled'."""
        self.ensure_one()
        if self.state == 'purchase_order':
            self.write({'state': 'cancelled'})
        else:
            raise UserError('Only purchase orders in the "purchase_order" state can be canceled.')

    def action_reset_to_draft(self):
        """Reset the purchase order to draft state."""
        self.ensure_one()
        if self.state == 'cancelled':
            raise UserError('Cancelled orders cannot be reset to draft.')
        self.write({'state': 'draft'})

    
    def action_create_receipt(self):
        self.ensure_one()  # Ensure we only process one record
 
        # Search for an existing receipt
        receipt = self.env['receipt.custom'].search([
            ('purchase_order_id', '=', self.id)
        ], limit=1)
 
        if not receipt:
            # Create a new receipt if one does not exist
            receipt = self.env['receipt.custom'].create({
                'purchase_order_id': self.id,
                # Additional fields can be populated if needed
            })
 
            # Pre-fill receipt lines from purchase order lines
            for line in self.order_line:
                self.env['receipt.order.line.custom'].create({
                    'receipt_order_id': receipt.id,
                    'product_category_id': line.product_category_id.id,
                    'product_id': line.product_id.id,
                    #'demand': line.total_quantity,  # Assuming demand matches total quantity
                    'product_qty': line.product_qty,  # Assuming quantity matches total quantity
                    'uom_id': line.uom_id.id,  # Use the primary UOM from purchase order line
                    'price_unit': line.price_unit,
                    'subtotal': line.subtotal,   
                })
 
        return {
            'type': 'ir.actions.act_window',
            'name': 'Receipt',
            'res_model': 'receipt.custom',
            'res_id': receipt.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }

    @api.onchange('supplier_id')
    def _onchange_supplier(self):
        """Populate land details and loans when a supplier is selected."""
        if self.supplier_id:
            # Populate land details
            self.land_ids = self.supplier_id.land_ids
            # Populate loans - the loans should only be those in 'loan' state
            self.loan_ids = self.supplier_id.loan_ids.filtered(lambda loan: loan.state == 'loan')
            # Ensure the remaining loan is recomputed
            # self._compute_remaining_loan()
        else:
            self.land_ids = False
            self.loan_ids = False
            # self.remaining_loan = 0.0  

# Purchase Order Line Custom Model
class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line.custom'
    _description = 'Purchase Order Line Custom'

    purchase_order_id = fields.Many2one('purchase.order.custom', string='Purchase Order', required=True)
    product_category_id = fields.Many2one('custom.product.category', string="Product Category", required=True)
    product_id = fields.Many2one('custom.product', string='Product', required=True, domain="[('product_category_id','=',product_category_id)]")
    product_qty = fields.Float(string='Quantity', required=True, default=1.0)
    category_id = fields.Many2one('custom.uom.category', string="UOM Category", required=True,
                                  default=lambda self: self.env['custom.uom.category'].search([('name', '=', 'Weight')], limit=1))
    uom_id = fields.Many2one('custom.uom', related='product_id.uom_id', string='Unit of Measure', store="true", domain="[('category_id','=',category_id)]")
    price_unit = fields.Float(string='Unit Price', related='product_id.cost_price', store=True)
    subtotal = fields.Float(string='Amount', compute='_compute_subtotal', store=True)
    

    @api.depends('product_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_qty * line.price_unit


# Receipt Custom Model
class Receipt(models.Model):
    _name = 'receipt.custom'
    _description = 'Receipt Custom'

    name = fields.Char(string='Receipt Number', required=True, copy=False, readonly=True, default='New')
    purchase_order_id = fields.Many2one('purchase.order.custom', string='Purchase Order', required=True)
    receipt_date = fields.Datetime(string='Receipt Date', default=fields.Datetime.now)
    # Add supplier and warehouse fields
    supplier_id = fields.Many2one('supplier.registration', string='Supplier', related='purchase_order_id.supplier_id', readonly=True)
    wh_loc_id = fields.Many2one('custom.inventory.warehouse', string='Warehouse location', related='purchase_order_id.wh_loc_id', readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('received', 'Received'), ('cancelled', 'Cancelled')], default='draft', string='Status')

    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    order_line_ids = fields.One2many('receipt.order.line.custom', 'receipt_order_id', string='Receipt Lines')
    
    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('receipt.custom.sequence')
        return super().create(vals)

    @api.depends('purchase_order_id.order_line')
    def _compute_total_amount(self):
        """Compute the total amount for the receipt based on purchase order lines."""
        for receipt in self:
            receipt.total_amount = sum(line.subtotal for line in receipt.purchase_order_id.order_line)
   
    def action_receive(self):
        """Receive the products in stock picking and create stock moves."""
        self.ensure_one()
        if self.state == 'draft':
            self.write({'state': 'received'})
   
    def action_create_invoice(self):
        self.ensure_one()  # Ensure we only process one record

        # Search for an existing Invoice
        invoice = self.env['purchase.invoice.custom'].search([
            ('receipt_id', '=', self.id)
        ], limit=1)

        if not invoice:
            # Create a new invoice if one does not exist
            invoice = self.env['purchase.invoice.custom'].create({
                'purchase_order_id': self.purchase_order_id.id,  # Ensure the purchase_order_id is set here
                'receipt_id': self.id,
                # Additional fields can be populated if needed
            })

            # Pre-fill invoice lines from purchase order lines
            for line in self.order_line_ids:
                self.env['invoice.order.line.custom'].create({
                    'invoice_order_id': invoice.id,
                    'product_category_id': line.product_category_id.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.product_qty,  # Assuming quantity matches total quantity
                    'uom_id': line.uom_id.id,  # Use the primary UOM from purchase order line
                    'price_unit': line.price_unit,
                    'subtotal': line.subtotal,
                })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'purchase.invoice.custom',
            'res_id': invoice.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }

# Receipt Order Line Custom Model
class ReceiptOrderLine(models.Model):
    _name = 'receipt.order.line.custom'
    _description = 'Receipt Order Line Custom'

    receipt_order_id = fields.Many2one('receipt.custom', string='Receipt ID', required=True)
    product_category_id = fields.Many2one('custom.product.category', string="Product Category", required=True)
    product_id = fields.Many2one('custom.product', string='Product', required=True, domain="[('product_category_id','=',product_category_id)]")
    product_qty = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('custom.uom', string='Unit of Measure', store="true")
    price_unit = fields.Float(string='Unit Price', store=True)
    subtotal = fields.Float(string='Amount')


# Purchase Invoice Custom Model
class PurchaseInvoice(models.Model):
    _name = 'purchase.invoice.custom'
    _description = 'Invoice Custom'

    name = fields.Char(string='Invoice Number', required=True, copy=False, readonly=True, default='New')
    receipt_id =fields.Many2one('receipt.custom', string='receipt')
    purchase_order_id = fields.Many2one('purchase.order.custom', string='Purchase Order', required=True)
    invoice_date = fields.Datetime(string='Invoice Date', default=fields.Datetime.now)
     # Add supplier and warehouse fields
    supplier_id = fields.Many2one('supplier.registration', string='Supplier', related='purchase_order_id.supplier_id', readonly=True)
    wh_loc_id = fields.Many2one('custom.inventory.warehouse', string='Warehouse location', related='purchase_order_id.wh_loc_id', readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted'), ('cancelled', 'Cancelled')], default='draft', string='Status')
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    order_line_ids = fields.One2many('invoice.order.line.custom', 'invoice_order_id', string='Invoice Lines')

    
    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.invoice.custom.sequence')
        return super().create(vals)

    @api.depends('purchase_order_id')
    def _compute_total_amount(self):
        """Compute the total amount for the invoice based on the purchase order."""
        for invoice in self:
            invoice.total_amount = invoice.purchase_order_id.amount_total

    def action_post(self):
        """Post the invoice."""
        self.ensure_one()
        if self.state == 'draft':
            self.write({'state': 'posted'})

    def action_cancel(self):
        """Cancel the invoice."""
        self.ensure_one()
        if self.state == 'posted':
            self.write({'state': 'cancelled'})
    
    def action_create_payment(self):
        """Create a payment linked to the purchase order and open the form view in a popup modal."""
        self.ensure_one()  # Ensure we only process one record

        # Search for an existing payment linked to this purchase order
        payment = self.env['purchase.payment.custom'].search([ 
            ('invoice_id.purchase_order_id', '=', self.purchase_order_id.id)
        ], limit=1)

        if not payment:
            # Create a new payment if one does not exist
            payment = self.env['purchase.payment.custom'].create({
                'invoice_id': self.id,  # Link the invoice directly
                'amount': self.total_amount,  # Use the total_amount from the invoice
                'state': 'draft',
                'name': self.env['ir.sequence'].next_by_code('purchase.payment.custom.sequence') or 'New',
            })

        # Return an action to open the form view in a popup modal
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment Form',
            'res_model': 'purchase.payment.custom',
            'res_id': payment.id,  # ID of the newly created payment
            'view_mode': 'form',  # Open the form view
            'view_type': 'form',
            'target': 'current',  # Open in a popup modal
        }


# Invoice Order Line Custom Model
class InvoiceOrderLine(models.Model):
    _name = 'invoice.order.line.custom'
    _description = 'Invoice Order Line Custom'

    invoice_order_id = fields.Many2one('purchase.invoice.custom', string='Invoice ID', required=True)
    product_category_id = fields.Many2one('custom.product.category', string="Product Category", required=True)
    product_id = fields.Many2one('custom.product', string='Product', required=True, domain="[('product_category_id','=',product_category_id)]")
    product_qty = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('custom.uom', string='Unit of Measure', store="true")
    price_unit = fields.Float(string='Unit Price', store=True)
    subtotal = fields.Float(string='Amount')

# Purchase Payment Custom Model
class PurchasePayment(models.Model):
    _name = 'purchase.payment.custom'
    _description = 'Payment Custom'

    name = fields.Char(string='Payment Number', required=True, copy=False, readonly=True, default='New')
    invoice_id = fields.Many2one('purchase.invoice.custom', string='Invoice', required=True)
    payment_date = fields.Date(string='Payment Date', default=fields.Date.today())
    supplier_id = fields.Many2one('supplier.registration', string='Supplier', related='invoice_id.supplier_id', readonly=True)
    wh_loc_id = fields.Many2one('custom.inventory.warehouse', string='Warehouse Location', related='invoice_id.wh_loc_id', readonly=True)
    amount = fields.Float(string='Amount', required=True)
    state = fields.Selection([('draft', 'Draft'), ('paid', 'Paid')], default='draft', string='Status')

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.payment.custom.sequence')
        return super().create(vals)

    def action_post(self):
        """Mark the payment as 'paid'."""
        self.ensure_one()
        if self.state == 'draft':
            self.write({'state': 'paid'})
            # Handle loan payment deduction if needed
            self._handle_loan_deduction()
            # Update physical inventory after payment
            self._update_physical_inventory()

    def _handle_loan_deduction(self):
        """Handle loan deduction logic if 'deduct_loan_amount' is checked on the purchase order."""
        purchase_order = self.invoice_id.purchase_order_id
        if purchase_order.deduct_loan_amount:
            loans_to_pay = self.env['custom.resource.share'].search([
                ('supplier_id', '=', purchase_order.supplier_id.id),
                ('state', '=', 'loan')
            ])
            for loan in loans_to_pay:
                loan.amount -= self.amount
                # Ensure amount does not go negative
                if loan.amount < 0:
                    loan.amount = 0

                # Set payment date to current date and time
                loan.payment_date = datetime.now()

                # If the loan is fully paid, mark the loan as 'paid'
                if loan.amount == 0:
                    loan.state = 'paid'
   
    def _update_physical_inventory(self):
        """Update physical inventory after payment is done for the purchase order."""
        # Retrieve the purchase order from the invoice
        purchase_order = self.invoice_id.purchase_order_id

        # Now, loop through each order line and update the corresponding inventory
        for line in purchase_order.order_line:
            product = line.product_id
            # Check if there is a corresponding 'custom.physical.inventory' record to update
            physical_inventory = self.env['custom.physical.inventory'].search([
                ('product_id', '=', product.id),
                ('wh_loc_id', '=', self.wh_loc_id.id)
            ], limit=1)

            if physical_inventory:
                # Update the quantity in the physical inventory record
                physical_inventory.sudo().write({
                    'quantity': physical_inventory.quantity + line.product_qty
                })
            else:
                # If no physical inventory record exists, create a new one
                self.env['custom.physical.inventory'].create({
                    'product_id': product.id,
                    'wh_loc_id': self.wh_loc_id.id,
                    'quantity': line.product_qty,
                })
