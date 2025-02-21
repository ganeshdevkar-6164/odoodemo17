from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import requests
import logging
_logger = logging.getLogger(__name__)



class CustomerInvoice(models.Model):
    _name = 'vighnahar_agro.customer_invoice'
    _description = 'Customer Invoice'
    _order = "id desc"

    name = fields.Char(string="Reference", default='New')
    
    party_id = fields.Many2one('vighnahar_agro.party', string="Party", required=True, domain=[('is_customer', '=', True)])
    date = fields.Datetime(string="Invoice Date", default=fields.Datetime.now)
    
    invoice_type = fields.Selection([('regular', 'Regular Invoice'), ('percentage', 'Downpayment(Percentage)'), ('fixed_amount', 'Downpayment(Fixed Amount)')], string='Invoice Type', default='regular')
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    state = fields.Selection([('draft', 'Draft'), ('invoice', 'Invoice'), ('cancel', 'Cancel'), ('payment', 'In Payment'),('downpayment','Downpayment'),('paid','Paid')], string='Status', default='draft', required=True)
    warehouse_id = fields.Many2one('vighnahar_agro.warehouse', string = "Warehouse", required=True)
    payment_id = fields.Many2one('vighnahar_agro.payment', string='Payment')
    payment_notification_date = fields.Datetime(string='Payment Notification Date')
    message_sent = fields.Boolean(string='Payment Reminder Sent', default=False)
    downpayment = fields.Float(string='Downpayment Amount', default=0.0,  readonly=True)
    remaining_amount = fields.Float(string='Remaining Amount', compute='_compute_remaining_amount', store=True)
    customer_invoice_line_ids = fields.One2many('vighnahar_agro.customer_invoice_line', 'customer_invoice_id', string='Invoice Lines', required=True)
    
    
    
    @api.depends('total_amount', 'downpayment')
    def _compute_remaining_amount(self):
        for record in self:
            record.remaining_amount = record.total_amount - record.downpayment
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.customer_invoice')
        return super().create(vals_list)

    @api.depends('customer_invoice_line_ids.total')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(line.total for line in record.customer_invoice_line_ids)

    def action_create(self):
        for rec in self:
            if rec.invoice_type == 'regular':
                rec.state = 'invoice'
                
            elif rec.invoice_type == 'percentage':
                # Open the Downpayment Wizard with the percentage field visible
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Downpayment Percentage',
                    'view_mode': 'form',
                    'res_model': 'vighnahar_agro.downpayment_wizard',
                    'target': 'new',
                    'context': {
                        'default_customer_invoice_id': rec.id,
                        'default_invoice_type': rec.invoice_type,  # Add context to specify the invoice type
                    }
                }
            elif rec.invoice_type == 'fixed_amount':
                # Open the Downpayment Wizard with the fixed amount field visible
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Downpayment Fixed Amount',
                    'view_mode': 'form',
                    'res_model': 'vighnahar_agro.downpayment_wizard',
                    'target': 'new',
                    'context': {
                        'default_customer_invoice_id': rec.id,
                        'default_invoice_type': rec.invoice_type,  # Add context to specify the invoice type
                    }
                }
            else:
                rec.state = 'draft'
            
            self._update_physical_inventory_stock()
            
            
            
    def _update_physical_inventory_stock(self):
        """ Update physical inventory stock when the invoice is created. """
        for rec in self:
            # Find the physical inventory record for the selected warehouse
            physical_inventory = self.env['vighnahar_agro.physical_inventory'].search([
                ('warehouse_id', '=', rec.warehouse_id.id)
            ], limit=1)
            
            if not physical_inventory:
                raise UserError(_("No physical inventory found for the selected warehouse: %s" % rec.warehouse_id.name))
            
            # Loop through each invoice line and update the corresponding inventory record
            for line in rec.customer_invoice_line_ids:
                # Find the corresponding inventory line for the product in the physical inventory
                inventory_line = self.env['vighnahar_agro.inventory_line'].search([
                    ('physical_inventory_id', '=', physical_inventory.id),
                    ('product_id', '=', line.product_id.id)
                ], limit=1)

                if inventory_line:
                    # Deduct the converted quantity from the on-hand quantity
                    if inventory_line.quantity >= line.converted_quantity:
                        inventory_line.quantity -= line.converted_quantity
                    else:
                        raise UserError(_("Not enough stock in the warehouse: %s \nfor the product: %s. \nAvailable quantity is: %s" %
                            (inventory_line.physical_inventory_id.warehouse_id.name, line.product_id.name, inventory_line.quantity)
                        ))
                else:
                    raise UserError(_("Product: %s not found in warehouse: %s" % (line.product_id.name, rec.warehouse_id.name)))
                
    #send whatsapp message using ultramsg api and payment_notification_date           
    def send_whatsapp_message(self, phone_number, message):
        """ Function to send WhatsApp message using UltraMsg API """
        instance_id = 'instance106882'  # Replace with your instance ID
        token = 'vqi4mooaiyd5ay5b'  # Replace with your API token
        url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
       
        payload = {
            "token": token,
            "to": phone_number.strip(),
            "body": message
        }

        response = requests.post(url, data=payload)
 
        if response.status_code == 200:
            _logger.info(f"WhatsApp message successfully sent to {phone_number}")
        else:
            _logger.error(f"Failed to send WhatsApp message to {phone_number}. Response: {response.text}")

    @api.model
    def send_payment_reminder(self):
        """Scheduled action to send payment reminders."""
        # Get invoices that are in the 'invoice' state and have a set payment_notification_date
        invoices = self.env['vighnahar_agro.customer_invoice'].search([
            ('state', 'in', ['invoice', 'downpayment']),  # Handle both 'invoice' and 'downpayment' states
            ('payment_notification_date', '!=', False),
            ('message_sent', '=', False),  # Check if message has not been sent yet
        ])

        for invoice in invoices:
            # Get current time in the same timezone as payment_notification_date
            current_time = fields.Datetime.now()
            payment_time = invoice.payment_notification_date
            
            if payment_time and current_time >= payment_time:
                # Send the reminder message if the invoice's payment notification date is due
                if invoice.party_id.contact:
                    party_name = invoice.party_id.name
                    message = f"Dear {party_name}, your payment of {invoice.name} is pending. Please make your payment."
                    self.send_whatsapp_message(invoice.party_id.contact, message)
                    _logger.info(f"Payment reminder sent to {invoice.party_id.contact}")

                    # Mark the message as sent for this invoice
                    invoice.message_sent = True


    @api.model
    def create_cron_job(self):
        """ Create the scheduled action (cron job) programmatically. """
        cron_model = self.env['ir.cron']
        existing_cron = cron_model.search([('name', '=', 'Send Payment Reminder Cron')])

        if not existing_cron:
            cron_model.create({
                'name': 'Send Payment Reminder Cron',
                'model_id': self.env.ref('vighnahar_agro.model_vighnahar_agro_customer_invoice').id,
                'state': 'code',
                'code': 'model.send_payment_reminder()',  # Method to call
                'interval_type': 'minutes',  # You can set this to minutes, hours, days, etc.
                'interval_number': 2,  # 1440 minutes = 1 day, adjust this based on your needs
                'numbercall': -1,  # Infinite execution
                'nextcall': fields.Datetime.now(),
            })

    @api.model
    def init(self):
        """ Initialize method to create the cron job when the module is installed """
        super(CustomerInvoice, self).init()
        self.create_cron_job()       
    
            
            
    def action_payment(self):
        for rec in self:
            payment_vals = {
                'customer_invoice_id': rec.id,
                'date': fields.Date.today(),
                'amount': rec.remaining_amount,
                'party_id': rec.party_id.id,
                'warehouse_id' : rec.warehouse_id.id,
                'invoice_type': rec.invoice_type,
                'payment_line_ids': [(0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'uom_id': line.uom_id.id,
                    'price': line.price,
                    'converted_quantity': line.converted_quantity,
                    'converted_uom_id': line.converted_uom_id.id,
                    'uom_category_id': line.uom_category_id.id,
                    'available_product_category_ids': [(6, 0, line.available_product_category_ids.ids)],
                }) for line in rec.customer_invoice_line_ids]
            }
            payment = self.env['vighnahar_agro.payment'].create(payment_vals)
            rec.payment_id = payment.id
            rec.state = 'payment'
            return {
                'type': 'ir.actions.act_window',
                'name': 'Payment',
                'view_mode': 'form',
                'res_model': 'vighnahar_agro.payment',
                'res_id': payment.id,
                'target': 'current',
            }

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'
    
   
    


class CustomerInvoiceLine(models.Model):
    _name = 'vighnahar_agro.customer_invoice_line'
    _description = 'Customer Invoice Line'

    customer_invoice_id = fields.Many2one('vighnahar_agro.customer_invoice', string='Invoice')
    uom_category_id = fields.Many2one('vighnahar_agro.uom_category', related='product_id.category_id', string='UOM Category')
    product_category_id = fields.Many2one('vighnahar_agro.product_category', string='Product Category', domain="[('id', 'in', available_product_category_ids)]")
    product_id = fields.Many2one('vighnahar_agro.product', string='Product', domain="[('product_category_id', '=', product_category_id)]", required=True)
    quantity = fields.Float(string='Quantity', digits=(16, 4))
    uom_id = fields.Many2one('vighnahar_agro.uom', string='UOM', domain="[('category_id', '=', uom_category_id)]")
    price = fields.Float(string='Unit Price', related='product_id.sales_price', store=True)
    total = fields.Float(string='Total Price', compute='_compute_total', store=True)
    converted_quantity = fields.Float(string='Converted Quantity', digits=(16, 4), compute='_compute_converted_quantity', store=True)
    converted_uom_id = fields.Many2one('vighnahar_agro.uom', string='Converted UOM', compute='_compute_converted_quantity', store=True)
    available_product_category_ids = fields.Many2many('vighnahar_agro.product_category', compute='_compute_available_product_categories', relation='vighnahar_agro_prod_cat_invoice_line_rel')
    
    is_available = fields.Boolean(
        string='Is Available',
        compute='_compute_is_available',
        store=False,
        help="Indicates if the converted quantity is available in the warehouse."
    )

    @api.depends('product_id', 'customer_invoice_id.warehouse_id', 'converted_quantity')
    def _compute_is_available(self):
        for line in self:
            if not line.product_id or not line.customer_invoice_id.warehouse_id:
                line.is_available = False
                continue

            # Find the physical inventory for the selected warehouse
            physical_inventory = self.env['vighnahar_agro.physical_inventory'].search([
                ('warehouse_id', '=', line.customer_invoice_id.warehouse_id.id)
            ], limit=1)

            if not physical_inventory:
                line.is_available = False
                continue

            # Find the inventory line for the product
            inventory_line = self.env['vighnahar_agro.inventory_line'].search([
                ('physical_inventory_id', '=', physical_inventory.id),
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            if inventory_line and line.converted_quantity <= inventory_line.quantity:
                line.is_available = True
            else:
                line.is_available = False
    
                
                
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
            product_ids = self.env['vighnahar_agro.product'].search([('can_be_sold', '=', True)])
            category_ids = product_ids.mapped('product_category_id')
            line.available_product_category_ids = category_ids


    
    




class Payment(models.Model):
    _name = 'vighnahar_agro.payment'
    _description = 'Payment'
    _order = "id desc"

    name = fields.Char(string="Reference", default='New')
    customer_invoice_id = fields.Many2one('vighnahar_agro.customer_invoice', string='Customer Invoice', required=True)
    party_id = fields.Many2one('vighnahar_agro.party', string="Party", required=True, domain=[('is_customer', '=', True)])
    date = fields.Date(string="Date", default=fields.Date.today)
    invoice_type = fields.Selection([('regular', 'Regular Invoice'), ('percentage', 'Downpayment(Percentage)'), ('fixed_amount', 'Downpayment(Fixed Amount)')], string='Invoice Type', default='regular')
    amount = fields.Float(string='Amount', compute='_compute_amount', store=True)
    state = fields.Selection([('draft', 'Draft'), ('paid', 'Paid')], string='Status', default='draft', required=True)
    warehouse_id = fields.Many2one('vighnahar_agro.warehouse', string = "Warehouse", required=True)
    payment_line_ids = fields.One2many('vighnahar_agro.payment_line', 'payment_id', string='Payment Lines')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.payment')
        return super().create(vals_list)
    


    def action_confirm_payment(self):
        for rec in self:
            # If it's a downpayment, assign the amount to the downpayment field of the invoice
            if rec.customer_invoice_id.state == 'downpayment':
                rec.customer_invoice_id.downpayment += rec.amount  # Adding the downpayment to the invoice's downpayment field
                rec.customer_invoice_id.state = 'downpayment'
            else:
                # If it's a regular payment, mark the invoice as paid
                rec.customer_invoice_id.state = 'paid'

            rec.state = 'paid'  # Change the payment status to 'paid'
            



class PaymentLine(models.Model):
    _name = 'vighnahar_agro.payment_line'
    _description = 'Payment Line'

    payment_id = fields.Many2one('vighnahar_agro.payment', string='Payment')
    product_id = fields.Many2one('vighnahar_agro.product', string='Product')
    quantity = fields.Float(string='Quantity', digits=(16, 4))
    uom_id = fields.Many2one('vighnahar_agro.uom', string='UOM')
    price = fields.Float(string='Unit Price')
    total = fields.Float(string='Total Price', compute='_compute_total', store=True)
    converted_quantity = fields.Float(string='Converted Quantity', digits=(16, 4), store=True)
    converted_uom_id = fields.Many2one('vighnahar_agro.uom', string='Converted UOM')
    uom_category_id = fields.Many2one('vighnahar_agro.uom_category', string='UOM Category')
    available_product_category_ids = fields.Many2many('vighnahar_agro.product_category', string='Available Product Categories')

    @api.depends('quantity', 'price')
    def _compute_total(self):
        for line in self:
            line.total = line.quantity * line.price
            
    
            



class DownpaymentWizard(models.TransientModel):
    _name = 'vighnahar_agro.downpayment_wizard'
    _description = 'Downpayment Wizard'

    customer_invoice_id = fields.Many2one('vighnahar_agro.customer_invoice', string='Customer Invoice', required=True)
    invoice_type = fields.Selection(related='customer_invoice_id.invoice_type', string='Invoice Type', readonly=True)
    percentage = fields.Float(string='Downpayment Percentage')
    fixed_amount = fields.Float(string='Downpayment Fixed Amount')

    @api.onchange('invoice_type')
    def _onchange_invoice_type(self):
        if self.invoice_type == 'percentage':
            # Show only percentage field and hide the fixed_amount field
            self.fixed_amount = False  # Reset fixed amount when invoice type is percentage
        elif self.invoice_type == 'fixed_amount':
            # Show only fixed_amount field and hide the percentage field
            self.percentage = 0.0  # Reset percentage when invoice type is fixed_amount
            
    def action_create_payment(self):
        """
        This method is called to create the payment based on the downpayment amount.
        If the invoice type is percentage, calculate the percentage of the total amount
        and create the payment with the corresponding details.
        """
        if self.invoice_type == 'percentage':
            downpayment_amount = self.customer_invoice_id.total_amount * (self.percentage / 100)
        elif self.invoice_type == 'fixed_amount':
            downpayment_amount = self.fixed_amount
        else:
            raise ValidationError(_("Invalid invoice type for downpayment."))

        # Check if the 'downpayment' product exists, if not, create it
        downpayment_product = self.env['vighnahar_agro.product'].search([('name', '=', 'Downpayment')], limit=1)
        if not downpayment_product:
            downpayment_product = self.env['vighnahar_agro.product'].create({
                'name': 'Downpayment',
                'product_type': 'service',  # assuming it's a service product
            })

        # Create a payment line for the downpayment product
        payment_line_vals = {
            'product_id': downpayment_product.id,
            'quantity': 1,
            'uom_id': downpayment_product.uom_id.id,  # Assuming default UOM is set for product
            'price': downpayment_amount,
            'total': downpayment_amount,
        }

        # Create the payment record
        payment_vals = {
            'customer_invoice_id': self.customer_invoice_id.id,
            'date': fields.Date.today(),
            'amount': downpayment_amount,
            'party_id': self.customer_invoice_id.party_id.id,
            'warehouse_id':self.customer_invoice_id.warehouse_id.id,
            'invoice_type': self.invoice_type,
            'payment_line_ids': [(0, 0, payment_line_vals)],
        }

        payment = self.env['vighnahar_agro.payment'].create(payment_vals)

        # Link the payment to the invoice
        self.customer_invoice_id.payment_id = payment.id
        self.customer_invoice_id.state = 'downpayment'

        # Return an action to open the payment form
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment',
            'view_mode': 'form',
            'res_model': 'vighnahar_agro.payment',
            'res_id': payment.id,
            'target': 'current',
        }