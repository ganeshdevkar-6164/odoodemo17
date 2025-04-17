from odoo import models, fields, api
from odoo.exceptions import ValidationError
import qrcode
from io import BytesIO
import base64

class SupplierInvoice(models.Model):
    _name = 'vighnahar_agro.supplier_invoice'
    _description = 'Supplier Invoice'
    _order = "id desc"
    
    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, index=True, default='New')
    description = fields.Text(string="Description")
    
    # Add is_labor checkbox field
    # is_labor = fields.Boolean(string="Is Labor", default=False)
    
    # Update the party_id field to filter only 'labor' parties if is_labor is True
    party_id = fields.Many2one('vighnahar_agro.party', string="Party/Supplier", required=True, domain=[('is_supplier', '=', True)] , ondelete='cascade')
    
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    total_amount_tax_excluded = fields.Float(string="Total Amount (Excluding Tax)", compute='_compute_total_amount_tax_excluded', store=True)
    tax_amount = fields.Float(string="Tax Amount", compute='_compute_tax_amount', store=True)
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    total_amount_tax_included = fields.Float(string="Total Amount (Including Tax)", compute='_compute_total_amount_tax_included', store=True)    
    warehouse_id = fields.Many2one('vighnahar_agro.warehouse', string = "Receiving Warehouse", required=True, ondelete='cascade')
    amount_due = fields.Float(string="Amount Due", compute='_compute_amount_due', store=True)
    paid_amount = fields.Float(string="Paid Amount", compute='_compute_total_paid', store=True)
    
    supplier_invoice_line_ids = fields.One2many('vighnahar_agro.supplier_invoice_line', 'invoice_id', string='Invoice Lines', ondelete='cascade')
    payment_ids = fields.One2many('vighnahar_agro.supplier_payment', 'invoice_id', string='Payments', ondelete='cascade')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('post', 'Posted'),
    ], default='draft', string="Invoice Status")
    
    payment_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ], compute='_compute_payment_status', string='Payment Status', default='draft', store=True)
    
    has_tax_lines = fields.Boolean(compute='_compute_has_tax_lines', string="Has Tax Lines", store=True)
    
    journal_id = fields.Many2one(
        'vighnahar_agro.journal', 
        string='Journal', 
        required=True, 
        domain=[('type', '=', 'purchase')],
        default=lambda self: self.env.ref('vighnahar_agro.journal_vendor_bill', raise_if_not_found=False )
    )
    journal_item_ids = fields.One2many('vighnahar_agro.journal_item', 'supplier_invoice_id', string="Journal Items" , ondelete='cascade')

    # Generate unique sequence number    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.supplier_invoice') or 'New'
        return super(SupplierInvoice, self).create(vals)
    
          
    @api.depends('supplier_invoice_line_ids.tax_ids')
    def _compute_has_tax_lines(self):
        for invoice in self:
            invoice.has_tax_lines = any(line.tax_ids for line in invoice.supplier_invoice_line_ids)
    
    # Calculate the total amount from invoice lines
    @api.depends('supplier_invoice_line_ids.tax_included_amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(line.tax_included_amount for line in record.supplier_invoice_line_ids)
    
    @api.depends('supplier_invoice_line_ids.tax_amount')
    def _compute_tax_amount(self):
        for invoice in self:
            invoice.tax_amount = sum(line.tax_amount for line in invoice.supplier_invoice_line_ids)
    
    @api.depends('supplier_invoice_line_ids.tax_excluded_amount')
    def _compute_total_amount_tax_excluded(self):
        for record in self:
            record.total_amount_tax_excluded = sum(line.tax_excluded_amount for line in record.supplier_invoice_line_ids)

    @api.depends('supplier_invoice_line_ids.tax_included_amount')
    def _compute_total_amount_tax_included(self):
        for record in self:
            record.total_amount_tax_included = sum(line.tax_included_amount for line in record.supplier_invoice_line_ids)

    @api.depends('total_amount', 'paid_amount')
    def _compute_amount_due(self):
        for record in self:
            record.amount_due = record.total_amount - record.paid_amount

    @api.depends('total_amount', 'paid_amount')
    def _compute_payment_status(self):
        for record in self:
            # _logger.info(f"Computing payment status for {record.id}: total_amount = {record.total_amount}, paid_amount = {record.paid_amount}")
            if not record.supplier_invoice_line_ids or record.total_amount == 0:
                record.payment_status = 'draft'
            elif record.paid_amount == record.total_amount:
                record.payment_status = 'paid'
            elif record.paid_amount > 0.0:
                record.payment_status = 'partial'
            else:
                record.payment_status = 'draft'

    @api.depends('payment_ids.amount', 'payment_ids.state')
    def _compute_total_paid(self):
        for record in self:
            record.paid_amount = sum(payment.amount for payment in record.payment_ids if payment.state == 'paid')

    # Action to create payment (when invoice is not yet fully paid)
    def action_register_payment(self):
        self.ensure_one()  # Ensure we're working with a single invoice
        
        # Calculate the remaining amount to be paid
        remaining_amount = self.total_amount - self.paid_amount
        
        # Get the first bank account of the party (supplier)
        default_bank_account = self.party_id.bank_account_ids[:1]
        
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
                'default_bank_account_id': default_bank_account.id if default_bank_account else False,  # Set default bank account
                'default_party_id': self.party_id.id,  # Set the default party (supplier)
            },
        }

    
    # Action to confirm the invoice(nachiket Update)
    def action_confirm(self):
        physical_inventory = self.env['vighnahar_agro.physical_inventory'].search([
            ('warehouse_id', '=', self.warehouse_id.id)], limit=1)
        
        if not physical_inventory:
            physical_inventory = self.env['vighnahar_agro.physical_inventory'].create({
                'warehouse_id': self.warehouse_id.id,
            })

        for line in self.supplier_invoice_line_ids:
            inventory_line = self.env['vighnahar_agro.inventory_line'].search([
                ('physical_inventory_id', '=', physical_inventory.id),
                ('product_category_id', '=', line.product_category_id.id),
                ('product_id', '=', line.product_id.id),
            ], limit=1)
            
            if inventory_line:
                inventory_line.write({'quantity': inventory_line.quantity + line.converted_quantity})
            else:
                self.env['vighnahar_agro.inventory_line'].create({
                    'physical_inventory_id': physical_inventory.id,
                    'product_category_id': line.product_category_id.id,
                    'product_id': line.product_id.id,
                    'quantity': line.converted_quantity,
                })
            
            supplier_info = self.env['vighnahar_agro.supplier_info'].search([
                ('product_id', '=', line.product_id.id),
                ('party_id', '=', self.party_id.id)
            ], limit=1)
            
            if not supplier_info:
                self.env['vighnahar_agro.supplier_info'].create({
                    'product_id': line.product_id.id,
                    'party_id': self.party_id.id,
                    'price': line.price,
                    'uom_id': line.converted_uom_id.id,
                    'min_qty': 1,
                })
        
        # Create Journal Entry based on the invoice details
        self._create_journal_entry()
        
        self.payment_status = 'pending'
        self.state = 'post'


    def _create_journal_entry(self):
        # Create a new journal entry
        journal_entry = self.env['vighnahar_agro.journal_entry'].create({
            'name': self.name,
            'date': self.date,
            'journal_id': self.journal_id.id,
            'state': 'draft',
            'party_id': self.party_id.id,  # Adding party_id to the journal entry
            'total_amount': self.total_amount,  # Adding total_amount to the journal entry
        })

        # Get the necessary accounts
        expense_account = self.env['vighnahar_agro.account'].search([('account_type', '=', 'expense')], limit=1)
        liability_account = self.env['vighnahar_agro.account'].search([('account_type', '=', 'liability')], limit=1)
        # ← replace generic tax lookup with your Purchase Tax (Input VAT) account:
        purchase_tax_account = self.env['vighnahar_agro.account'].search([('code', '=', '2101')], limit=1)

        # Raise an error if any necessary account is missing
        if not expense_account:
            raise ValidationError("Expense account is missing. Please configure it in the chart of accounts.")
        if not liability_account:
            raise ValidationError("Liability account is missing. Please configure it in the chart of accounts.")
        if not purchase_tax_account:
            raise ValidationError("Purchase Tax (Input VAT) account (code 2101) is missing. Please configure it.")
        
        # Initialize lists for journal items
        journal_items = []
        total_debit = 0.0
        total_credit = 0.0

        # Loop through invoice lines and create journal items
        for line in self.supplier_invoice_line_ids:
            # Get tax-related data if applicable
            tax_id = line.tax_ids[:1] if line.tax_ids else None  # Take the first tax if available
            tax_amount = line.tax_amount if tax_id else 0.0  # Calculate tax amount if available

            # Expense Debit (purchase of goods or services)
            journal_items.append((0, 0, {
                'entry_id': journal_entry.id,
                'account_id': expense_account.id,
                'party_id': self.party_id.id,
                'debit': line.tax_excluded_amount,
                'credit': 0.0,
                'date': self.date,
                'product_id': line.product_id.id if line.product_id else False,
                'supplier_invoice_id': self.id,
                'tax_id': tax_id.id if tax_id else False,
            }))
            total_debit += line.tax_excluded_amount

            # Tax Debit (if applicable)
            if tax_id:
                journal_items.append((0, 0, {
                    'entry_id': journal_entry.id,
                    'account_id': purchase_tax_account.id,
                    'party_id': self.party_id.id,
                    'debit': tax_amount,
                    'credit': 0.0,
                    'date': self.date,
                    'supplier_invoice_id': self.id,
                    'tax_id': tax_id.id if tax_id else False,
                }))
                total_debit += tax_amount

            # Liability Credit (Accounts Payable)
            journal_items.append((0, 0, {
                'entry_id': journal_entry.id,
                'account_id': liability_account.id,
                'party_id': self.party_id.id,
                'debit': 0.0,
                'credit': line.tax_included_amount,
                'date': self.date,
                'product_id': line.product_id.id if line.product_id else False,
                'supplier_invoice_id': self.id,
            }))
            total_credit += line.tax_included_amount

        # Validation to ensure Debit and Credit are equal
        if round(total_debit, 2) != round(total_credit, 2):
            raise ValidationError(f"Total debit ({total_debit}) and credit ({total_credit}) are not equal! Please check the invoice details.")

        # Update journal entry with journal items and post the entry
        self.write({'journal_item_ids': journal_items})
        journal_entry.post_entry()

class SupplierInvoiceLine(models.Model):
    _name = 'vighnahar_agro.supplier_invoice_line'
    _description = 'Supplier Invoice Line'

    invoice_id = fields.Many2one('vighnahar_agro.supplier_invoice', string='Invoice', ondelete='cascade')
    uom_category_id = fields.Many2one('vighnahar_agro.uom_category', related='product_id.category_id', string='UOM Category')
    product_category_id = fields.Many2one('vighnahar_agro.product_category', string='Product Category', domain="[('id', 'in', available_product_category_ids)]" , ondelete='cascade')
    product_id = fields.Many2one('vighnahar_agro.product', string='Product', domain="[('product_category_id', '=', product_category_id)]" , ondelete='cascade')
    quantity = fields.Float(string='Quantity', digits=(16, 4))
    uom_id = fields.Many2one('vighnahar_agro.uom', string='UOM', domain="[('category_id', '=', uom_category_id)]" , ondelete='cascade')
    price = fields.Float(string='Unit Price', store=True, required = True)
    
    converted_quantity = fields.Float(string='Converted Quantity', digits=(16, 4), compute='_compute_converted_quantity', store=True)
    converted_uom_id = fields.Many2one('vighnahar_agro.uom', string='Converted UOM', compute='_compute_converted_quantity', store=True , ondelete='cascade')
    available_product_category_ids = fields.Many2many('vighnahar_agro.product_category', compute='_compute_available_product_categories')
    
    # Field to select taxes
    tax_ids = fields.Many2many('vighnahar_agro.account_tax', string="Taxes", domain=[('active', '=', True)],
                               relation='vighnahar_agro_supplier_invoice_line_account_tax_rel')
    tax_excluded_amount = fields.Float(string='Tax Excluded Amount', compute='_compute_tax_excluded_amount', store=True)
    tax_amount = fields.Float(string='Tax Amount', compute='_compute_tax_amount', store=True)
    tax_included_amount = fields.Float(string='Tax Included Amount', compute='_compute_tax_included_amount', store=True)
    
    @api.depends('converted_quantity', 'price')
    def _compute_tax_excluded_amount(self):
        for line in self:
            line.tax_excluded_amount = line.converted_quantity * line.price

    @api.depends('tax_ids', 'tax_excluded_amount')
    def _compute_tax_amount(self):
        for line in self:
            total_tax = 0.0
            for tax in line.tax_ids:
                total_tax += (tax.amount / 100) * line.tax_excluded_amount
            line.tax_amount = total_tax

    @api.depends('tax_excluded_amount', 'tax_amount')
    def _compute_tax_included_amount(self):
        for line in self:
            line.tax_included_amount = line.tax_excluded_amount + line.tax_amount

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

    @api.depends('product_id')
    def _compute_available_product_categories(self):
        for line in self:
            product_ids = self.env['vighnahar_agro.product'].search([('can_be_purchased', '=', True)])
            category_ids = product_ids.mapped('product_category_id')
            line.available_product_category_ids = category_ids


    @api.onchange('product_id', 'invoice_id.party_id')
    def _onchange_product_id(self):
        """Set the price and UOM from supplier info if available; otherwise, use product cost price and default UOM."""
        if self.product_id:
            supplier_info = self.env['vighnahar_agro.supplier_info'].search([
                ('product_id', '=', self.product_id.id),
                ('party_id', '=', self.invoice_id.party_id.id)
            ], limit=1)

            if supplier_info:
                self.price = supplier_info.price  # Use last purchased price
                self.uom_id = supplier_info.uom_id  # Use the UOM from supplier info
            else:
                self.price = self.product_id.cost_price  # Use product's cost price
                self.uom_id = self.product_id.uom_id  # Use product's default UOM


class SupplierPayment(models.Model):
    _name = 'vighnahar_agro.supplier_payment'
    _description = 'Supplier Payment'
    _order = "id desc"
    
    name = fields.Char(string="Payment Reference", required=True, copy=False, readonly=True, index=True, default='New')
    payment_date = fields.Date(string='Payment Date', default=fields.Date.today)
    amount = fields.Float(string="Amount", required=True)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online')
    ], string="Payment Method", required=True, default='cash')
    invoice_id = fields.Many2one('vighnahar_agro.supplier_invoice', string='Supplier Invoice', required=True , ondelete='cascade')
    state = fields.Selection([('draft', 'Draft'), ('paid', 'Paid'), ('cancel', 'Cancelled')], string="Payment Status", default='draft')
    party_id = fields.Many2one('vighnahar_agro.party', string="Party")
    bank_account_id = fields.Many2one('vighnahar_agro.bank_account', string = "Bank Account" , ondelete='cascade',domain="[('party_id', '=', party_id)]")
    
    
    # New field to store the QR code
    qr_code_image = fields.Image(string="Payment QR Code", compute='_generate_qr_code', store=True)

    @api.depends('payment_method', 'bank_account_id.upi_id', 'amount')
    def _generate_qr_code(self):
        for record in self:
            if record.payment_method == 'online' and record.bank_account_id and record.bank_account_id.upi_id:
                # Generate the UPI URI with amount included
                upi_uri = f"upi://pay?pa={record.bank_account_id.upi_id}&am={record.amount}&cu=INR&tn=Payment%20for%20Invoice%20{record.invoice_id.name}"
                
                # Generate QR code
                qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
                qr.add_data(upi_uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                # Convert the image to base64 and store in the field
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                qr_code_image_base64 = base64.b64encode(buffer.getvalue())
                buffer.close()

                # Store the QR code in the field
                record.qr_code_image = qr_code_image_base64
            else:
                record.qr_code_image = False
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.supplier_payment') or 'New'
        return super(SupplierPayment, self).create(vals)

    def action_pay(self):
        self.ensure_one()

        if self.payment_method == 'online':
            
            # Check if the bank account has a valid UPI ID
            if not self.bank_account_id or not self.bank_account_id.upi_id:
                raise ValidationError("Online payment requires a bank account with a UPI ID.")
            
            # Generate the QR code and open the wizard to display it
            return {
                'name': 'UPI Payment QR Code',
                'type': 'ir.actions.act_window',
                'res_model': 'vighnahar_agro.supplier_payment_qr_wizard',
                'view_mode': 'form',
                'view_id': self.env.ref('vighnahar_agro.view_supplier_payment_qr_wizard_form').id,
                'target': 'new',
                'context': {
                    'default_payment_id': self.id,
                    'default_qr_code_image': self.qr_code_image,
                    'default_amount': self.amount
                    
                }
            }
        elif self.payment_method == 'bank':
            # Pass bank details to the wizard for bank payment method
            return {
                'name': 'Bank Payment Details',
                'type': 'ir.actions.act_window',
                'res_model': 'vighnahar_agro.supplier_payment_bank_wizard',
                'view_mode': 'form',
                'view_id': self.env.ref('vighnahar_agro.view_supplier_payment_bank_wizard_form').id,
                'target': 'new',
                'context': {
                    'default_payment_id': self.id,
                    'default_bank_name': self.bank_account_id.banks_id.name,
                    'default_account_number': self.bank_account_id.name,
                    'default_branch': self.bank_account_id.branch,
                    'default_ifsc_code': self.bank_account_id.ifsc_code,
                    'default_bank_holder_name': self.bank_account_id.party_id.name,  # Bank Holder Name
                    'default_amount': self.amount,  # Amount to pay
                    'default_invoice_number': self.invoice_id.name,
                }
            }
        else:
            # If payment_method is anything else, update the payment status directly
            self.state = 'paid'
            self.invoice_id.payment_ids |= self  # Link payment to invoice
            # Optionally, update the invoice's total paid amount
            paid_amount = sum(payment.amount for payment in self.invoice_id.payment_ids if payment.state == 'paid')
            self.invoice_id.paid_amount = paid_amount
            
    
    
    @api.model
    def default_get(self, fields):
        res = super(SupplierPayment, self).default_get(fields)
        
        if 'invoice_id' in res:
            invoice = self.env['vighnahar_agro.supplier_invoice'].browse(res['invoice_id'])
            if invoice and invoice.party_id.bank_account_ids:
                res['bank_account_id'] = invoice.party_id.bank_account_ids[:1].id  # Get first bank account
        
        return res


class SupplierPaymentQRCodeWizard(models.TransientModel):
    _name = 'vighnahar_agro.supplier_payment_qr_wizard'
    _description = 'Supplier Payment QR Code Wizard'
    
    payment_id = fields.Many2one('vighnahar_agro.supplier_payment', string="Supplier Payment")
    qr_code_image = fields.Image(string="Payment QR Code")
    amount = fields.Float(string="Amount")
    
    @api.model
    def default_get(self, fields):
        res = super(SupplierPaymentQRCodeWizard, self).default_get(fields)

        # Set the QR code image from the context (generated in the SupplierPayment model)
        if 'default_qr_code_image' in self.env.context:
            res['qr_code_image'] = self.env.context.get('default_qr_code_image')

        return res
    
    def action_done(self):
        # Update the payment state to 'paid'
        self.payment_id.state = 'paid'
        # Show success animation
        return {
            'name': 'Payment Successful',
            'type': 'ir.actions.act_window',
            'res_model': 'vighnahar_agro.payment_success_wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('vighnahar_agro.view_payment_success_wizard_form').id,
            'target': 'new',
            'context': {
                'default_payment_amount': self.amount,
                'default_payment_method': 'UPI Payment',
            }
        }

    def action_cancel(self):
        # Update the payment state to 'cancel' when Cancel is clicked
        self.payment_id.state = 'cancel'
        # Close the wizard
        return {'type': 'ir.actions.act_window_close'}
    
    

class SupplierPaymentBankWizard(models.TransientModel):
    _name = 'vighnahar_agro.supplier_payment_bank_wizard'
    _description = 'Supplier Payment Bank Wizard'

    # Add fields to capture bank details in the wizard
    payment_id = fields.Many2one('vighnahar_agro.supplier_payment', string="Supplier Payment")
    bank_name = fields.Char(string="Bank Name")
    account_number = fields.Char(string="Account Number")
    branch = fields.Char(string="Branch")
    ifsc_code = fields.Char(string="IFSC Code")
    bank_holder_name = fields.Char(string="Bank Holder Name")  # Bank Holder Name field
    amount = fields.Float(string="Amount to Pay")  # Amount to Pay field
    invoice_number = fields.Char(string="Invoice Number")  # Invoice Number field

    def action_done(self):
        # Update payment state and link to invoice
        self.payment_id.state = 'paid'
        # Show success animation
        return {
            'name': 'Payment Successful',
            'type': 'ir.actions.act_window',
            'res_model': 'vighnahar_agro.payment_success_wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('vighnahar_agro.view_payment_success_wizard_form').id,
            'target': 'new',
            'context': {
                'default_payment_amount': self.amount,
                'default_payment_method': 'Bank Transfer',
            }
        }
    
    def action_cancel(self):
        """Set the payment state to 'cancel' when Cancel is clicked and close the wizard."""
        self.payment_id.state = 'cancel'
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields):
        res = super(SupplierPaymentBankWizard, self).default_get(fields)
        
        # Retrieve the bank details, holder name, amount, and invoice number from context
        if 'default_bank_name' in self.env.context:
            res['bank_name'] = self.env.context.get('default_bank_name')
        if 'default_account_number' in self.env.context:
            res['account_number'] = self.env.context.get('default_account_number')
        if 'default_branch' in self.env.context:
            res['branch'] = self.env.context.get('default_branch')
        if 'default_ifsc_code' in self.env.context:
            res['ifsc_code'] = self.env.context.get('default_ifsc_code')
        if 'default_bank_holder_name' in self.env.context:
            res['bank_holder_name'] = self.env.context.get('default_bank_holder_name')  # Populate Bank Holder Name
        if 'default_amount' in self.env.context:
            res['amount'] = self.env.context.get('default_amount')  # Populate Amount to Pay
        if 'default_invoice_number' in self.env.context:
            res['invoice_number'] = self.env.context.get('default_invoice_number')  # Populate Invoice Number

        return res
    
    
class PaymentSuccessWizard(models.TransientModel):
    _name = 'vighnahar_agro.payment_success_wizard'
    _description = 'Payment Success Animation Wizard'

    payment_amount = fields.Float(string="Amount Paid", readonly=True)
    payment_method = fields.Char(string="Payment Method", readonly=True)
