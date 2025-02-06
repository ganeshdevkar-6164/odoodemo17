from odoo import models, fields, api
from odoo.exceptions import UserError

class CustomResourceShare(models.Model):
    _name = 'custom.resource.share'
    _description = 'Custom Resource Share'

    name = fields.Char(string="Resource Name", required=True)
    supplier_id = fields.Many2one('supplier.registration', string="Supplier", required=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.today())  # Default date to today

    # State to manage different stages
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('loan', 'Loan'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], default='draft', string="State", required=True)

    # Fields related to loan and payment
    amount = fields.Float(string="Amount", compute="_compute_amount", store=True)
    payment_date = fields.Date(string="Payment Date")
    loan_amount = fields.Float(string="Loan Amount", readonly=True) 
    loan_ids = fields.One2many('custom.resource.share.line', 'resource_share_id', string="Loans")
    product_ids = fields.One2many('custom.resource.share.line', 'resource_share_id', string="Products/Fertilizers")

    # New field: Remaining Loan Balance
    remaining_loan_balance = fields.Float(string="Remaining Loan Balance", compute='_compute_remaining_loan_balance', store=True)


    @api.depends('product_ids.total_amount')
    def _compute_amount(self):
        """Compute the total amount based on the selected products"""
        for record in self:
            record.amount = sum(record.product_ids.mapped('total_amount'))

    @api.depends('loan_ids.state', 'loan_ids.total_amount')
    def _compute_remaining_loan_balance(self):
        """ Compute the remaining loan balance for the resource share """
        for record in self:
            # Sum the total amounts for loans in 'loan' state
            remaining_balance = sum(line.total_amount for line in record.loan_ids if line.state == 'loan')
            record.remaining_loan_balance = remaining_balance

    @api.model
    def create(self, vals):
        """Override the create method to handle state transitions."""
        vals['date'] = fields.Date.today()  # Ensure the date is set to today
        return super(CustomResourceShare, self).create(vals)

    def confirm_resource(self):
        """Action to confirm the resource"""
        if self.state != 'draft':
            raise UserError("You can only confirm a resource in draft state.")
        self.write({'state': 'confirmed'})

    def cancel_resource(self):
        """Action to cancel the resource"""
        if self.state == 'paid':
            raise UserError("Cannot cancel a paid resource.")
        self.write({'state': 'cancelled'})

    def reset_to_draft(self):
        """Action to reset to draft"""
        if self.state in ['confirmed', 'loan', 'paid']:
            raise UserError("You cannot reset a confirmed, loan, or paid resource to draft.")
        self.write({'state': 'draft'})

    def create_loan(self):
        """Create a loan against the selected supplier"""
        if self.state != 'confirmed':
            raise UserError("You can only create a loan for a confirmed resource.")
        
        self.write({
            'loan_amount': self.amount,  # Set loan amount
            'state': 'loan',  # Change state to loan
            'payment_date': None,  # No payment date yet for a loan
        })

    def make_immediate_payment(self):
        """Make an immediate payment"""
        if self.state not in ['confirmed', 'loan']:
            raise UserError("You can only make a payment for a confirmed or loaned resource.")
        
        self.write({'state': 'paid', 'payment_date': fields.Date.today()})

    def view_loans(self):
        """View all loans related to the current resource share"""
        loaned_products = self.product_ids.filtered(lambda p: p.state == 'loan')
        
        if not loaned_products:
            raise UserError("No loans are associated with this resource share.")
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'custom.resource.share.line',
            'view_mode': 'tree,form',
            'domain': [('resource_share_id', '=', self.id), ('state', '=', 'loan')],
            'target': 'current',
        }

class CustomResourceShareLine(models.Model):
    _name = 'custom.resource.share.line'
    _description = 'Custom Resource Share Line'

    resource_share_id = fields.Many2one('custom.resource.share', string="Resource Share", required=True)
    product_id = fields.Many2one('custom.product', string="Product", required=True)
    uom_id = fields.Many2one('custom.uom', string="UOM", related='product_id.uom_id', store=True, readonly=False)
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    total_amount = fields.Float(string="Total Amount", compute='_compute_total_amount', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('loan', 'Loan'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], default='draft', string="State", required=True)

    @api.depends('product_id', 'uom_id', 'quantity')
    def _compute_total_amount(self):
        for record in self:
            if record.product_id and record.uom_id:
                # Compute total amount considering the product's sales price and UOM factor
                uom_factor = record.uom_id.factor  # Assuming `factor` field exists in UOM model
                record.total_amount = record.product_id.sales_price * record.quantity * uom_factor
            else:
                record.total_amount = 0.0
