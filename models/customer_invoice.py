from odoo import models, fields, api, _
from odoo.tools.translate import _
from odoo.tools import format_date
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import requests
import logging
_logger = logging.getLogger(__name__)
import base64


class CustomerInvoice(models.Model):
    _name = 'vighnahar_agro.customer_invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Customer Invoice'
    _order = "id desc"

    name = fields.Char(string="Reference", default='New')
    
    party_id = fields.Many2one('vighnahar_agro.party', string="Party", required=True, domain=[('is_customer', '=', True)])
    date = fields.Datetime(string="Invoice Date", default=fields.Datetime.now)
    
    invoice_type = fields.Selection([('regular', 'Regular Invoice'), ('percentage', 'Downpayment(Percentage)'), ('fixed_amount', 'Downpayment(Fixed Amount)')], string='Invoice Type', default='regular', required=True)
    # total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    state = fields.Selection([('draft', 'Draft'), ('invoice', 'Invoice'), ('cancel', 'Cancel'), ('payment', 'In Payment'),('downpayment','Downpayment'),('paid','Paid')], string='Status', default='draft', required=True)
    warehouse_id = fields.Many2one('vighnahar_agro.warehouse', string = "Warehouse", required=True , ondelete='cascade')
    payment_id = fields.Many2one('vighnahar_agro.payment', string='Payment' , ondelete='cascade')
    payment_notification_date = fields.Datetime(string='Payment Notification Date')
    message_sent = fields.Boolean(string='Payment Reminder Sent', default=False)
    downpayment = fields.Float(string='Downpayment Amount', default=0.0,  readonly=True)
    remaining_amount = fields.Float(string='Remaining Amount', compute='_compute_remaining_amount', store=True)
    customer_invoice_line_ids = fields.One2many('vighnahar_agro.customer_invoice_line', 'customer_invoice_id', string='Invoice Lines', required=True , ondelete='cascade')
    
    total_amount_tax_excluded = fields.Float(string="Total Amount (Excluding Tax)", compute='_compute_total_amount_tax_excluded', store=True)
    tax_amount = fields.Float(string="Tax Amount", compute='_compute_tax_amount', store=True)
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    total_amount_tax_included = fields.Float(string="Total Amount (Including Tax)", compute='_compute_total_amount_tax_included', store=True)    
    journal_id = fields.Many2one('vighnahar_agro.journal', string='Journal', required=True, domain=[('type', '=', 'sale')] , ondelete='cascade', 
                                 default=lambda self: self.env.ref('vighnahar_agro.journal_customer_invoice', raise_if_not_found=False))
    journal_item_ids = fields.One2many('vighnahar_agro.journal_item', 'customer_invoice_id', string="Journal Items" , ondelete='cascade')
    has_tax_lines = fields.Boolean(compute='_compute_has_tax_lines', string="Has Tax Lines", store=True)

    
    @api.depends('total_amount', 'downpayment')
    def _compute_remaining_amount(self):
        for record in self:
            record.remaining_amount = record.total_amount - record.downpayment
    
    @api.model
    def create_invoice_report_action(self):
        """Ensure the report action and external ID exist."""
        report_name = 'vighnahar_agro.report_invoice_custom'
        external_id = 'action_report_invoice_custom'
        module_name = 'vighnahar_agro'

        Report = self.env['ir.actions.report'].sudo()
        ModelData = self.env['ir.model.data'].sudo()

        # Check if external ID exists
        model_data = ModelData.search([
            ('name', '=', external_id),
            ('module', '=', module_name),
            ('model', '=', 'ir.actions.report'),
        ], limit=1)

        if model_data:
            _logger.info("Report external ID already exists.")
            return

        # Try to find report by report_name
        existing_report = Report.search([('report_name', '=', report_name)], limit=1)

        if not existing_report:
            # Create the report action if not found
            existing_report = Report.create({
                'name': 'Customer Invoice Report',
                'model': 'vighnahar_agro.customer_invoice',
                'report_type': 'qweb-pdf',
                'report_name': report_name,
                'print_report_name': "'Customer Invoice - %s' % (object.name)",
            })
            _logger.info("Created report action: %s", existing_report)

        # Now register the external ID
        ModelData.create({
            'name': external_id,
            'model': 'ir.actions.report',
            'module': module_name,
            'res_id': existing_report.id,
            'noupdate': True,
        })
        _logger.info("Created external ID for report action: %s", external_id)
    
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.customer_invoice')
        return super().create(vals_list)

    @api.depends('customer_invoice_line_ids.tax_ids')
    def _compute_has_tax_lines(self):
        for invoice in self:
            invoice.has_tax_lines = any(line.tax_ids for line in invoice.customer_invoice_line_ids)
    
    # Calculate the total amount from invoice lines
    @api.depends('customer_invoice_line_ids.tax_included_amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(line.tax_included_amount for line in record.customer_invoice_line_ids)
    
    @api.depends('customer_invoice_line_ids.tax_amount')
    def _compute_tax_amount(self):
        for invoice in self:
            invoice.tax_amount = sum(line.tax_amount for line in invoice.customer_invoice_line_ids)
    
    @api.depends('customer_invoice_line_ids.tax_excluded_amount')
    def _compute_total_amount_tax_excluded(self):
        for record in self:
            record.total_amount_tax_excluded = sum(line.tax_excluded_amount for line in record.customer_invoice_line_ids)

    @api.depends('customer_invoice_line_ids.tax_included_amount')
    def _compute_total_amount_tax_included(self):
        for record in self:
            record.total_amount_tax_included = sum(line.tax_included_amount for line in record.customer_invoice_line_ids)

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
            
            self._create_journal_entry()  # Create a journal entry for the invoice
            
            self._update_physical_inventory_stock()
            
            # rec.send_invoice_email()
    
    def _create_journal_entry(self):
        # Create a new journal entry
        journal_entry = self.env['vighnahar_agro.journal_entry'].create({
            'name': self.name,
            'date': self.date,
            'journal_id': self.journal_id.id,
            'state': 'draft',
            'party_id': self.party_id.id,  # Adding party_id to the journal entry (customer)
            'total_amount': self.total_amount,  # Adding total_amount to the journal entry
        })

        # Get the necessary accounts
        revenue_account = self.env['vighnahar_agro.account'].search([('account_type', '=', 'revenue')], limit=1)
        receivable_account = self.env['vighnahar_agro.account'].search([('account_type', '=', 'receivable')], limit=1)
        # → Instead of the old generic tax account, fetch your Sales Tax (Output VAT) account:
        sales_tax_account = self.env['vighnahar_agro.account'].search([('code', '=', '2100')], limit=1)

        # Raise an error if any necessary account is missing
        if not revenue_account:
            raise ValidationError("Revenue account is missing. Please configure it in the chart of accounts.")
        if not receivable_account:
            raise ValidationError("Receivable account is missing. Please configure it in the chart of accounts.")
        if not sales_tax_account:
            raise ValidationError("Sales Tax (Output VAT) account is missing. Please configure account code 2100.")
        
        # Initialize lists for journal items
        journal_items = []
        total_debit = 0.0
        total_credit = 0.0

        # Loop through invoice lines and create journal items
        for line in self.customer_invoice_line_ids:
            # Get tax-related data if applicable
            tax_id = line.tax_ids[:1] if line.tax_ids else None  # Take the first tax if available
            tax_amount = line.tax_amount if tax_id else 0.0  # Calculate tax amount if available

            # Revenue Credit (sales of goods or services)
            journal_items.append((0, 0, {
                'entry_id': journal_entry.id,
                'account_id': revenue_account.id,
                'party_id': self.party_id.id,
                'debit': 0.0,
                'credit': line.tax_excluded_amount,
                'date': self.date,
                'product_id': line.product_id.id if line.product_id else False,
                'customer_invoice_id': self.id,
                'tax_id': tax_id.id if tax_id else False,
            }))
            total_credit += line.tax_excluded_amount

            # Tax Credit (if applicable)
            if tax_id:
                journal_items.append((0, 0, {
                    'entry_id': journal_entry.id,
                    'account_id': sales_tax_account.id,
                    'party_id': self.party_id.id,
                    'debit': 0.0,
                    'credit': tax_amount,
                    'date': self.date,
                    'customer_invoice_id': self.id,
                    'tax_id': tax_id.id if tax_id else False,
                }))
                total_credit += tax_amount

            # Receivable Debit (Accounts Receivable)
            journal_items.append((0, 0, {
                'entry_id': journal_entry.id,
                'account_id': receivable_account.id,
                'party_id': self.party_id.id,
                'debit': line.tax_included_amount,  # Total amount including tax
                'credit': 0.0,
                'date': self.date,
                'product_id': line.product_id.id if line.product_id else False,
                'customer_invoice_id': self.id,
            }))
            total_debit += line.tax_included_amount

        # Validation to ensure Debit and Credit are equal
        if round(total_debit, 2) != round(total_credit, 2):
            raise ValidationError(f"Total debit ({total_debit}) and credit ({total_credit}) are not equal! Please check the invoice details.")

        # Update journal entry with journal items and post the entry
        self.write({'journal_item_ids': journal_items})
        journal_entry.post_entry()

    def send_invoice_email(self):
        for invoice in self:
            if not invoice.party_id.email:
                raise UserError("Customer does not have an email address.")

            # ✅ Get the report action
            report_action = self.env.ref('vighnahar_agro.action_report_customer_invoice')

            # ✅ Correct way to render QWeb PDF for custom model
            pdf_content, content_type = self.env['ir.actions.report']._render_qweb_pdf(
                report_ref=report_action,
                res_ids=[invoice.id]
            )

            # Create PDF attachment
            attachment = self.env['ir.attachment'].create({
                'name': f'Invoice_{invoice.name}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': invoice._name,
                'res_id': invoice.id,
                'mimetype': 'application/pdf',
            })

            # Compose the HTML email body
            body_html = f"""
                <p>Dear {invoice.party_id.name},</p>
                <p>Thank you for your business. Please find your invoice attached below:</p>
                <p><strong>Invoice Number:</strong> {invoice.name}<br/>
                <strong>Total Amount:</strong> ₹{invoice.total_amount:.2f}</p>
                <p>Please contact us if you have any questions regarding this invoice.</p>
                <p>Thanks,<br/>
                Vighnahar Agro</p>
            """

            # Send email
            mail_values = {
                'subject': f'Invoice {invoice.name}',
                'body_html': body_html,
                'email_to': invoice.party_id.email,
                'attachment_ids': [(6, 0, [attachment.id])],
                'auto_delete': True,
            }

            mail = self.env['mail.mail'].create(mail_values)
            mail.send()

        
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
                
    # send whatsapp message using ultramsg api and payment_notification_date           
    def send_whatsapp_message(self, phone_number, message):
        """ Function to send WhatsApp message using UltraMsg API """
        instance_id = 'instance107303'  # Replace with your instance ID
        token = 'mpvx9yyty0vm5v5w'  # Replace with your API token
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
            ('state', 'in', ['invoice', 'downpayment','payment']),  # Handle both 'invoice' and 'downpayment' states
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
                    # message = f"Dear {party_name}, your payment of {invoice.name} is pending. Please make your payment."
                    invoice_number = invoice.name
                    remaining_amount = invoice.remaining_amount
                    due_date = invoice.payment_notification_date.strftime('%Y-%m-%d')  # Format the due date

                    # Construct the reminder message
                    message = f"""
                                Hello {party_name},
                                Your payment of Rs. {remaining_amount} is pending for Invoice #{invoice_number}, due on {due_date}. Kindly make the payment at your earliest convenience to avoid any disruption.
                                If you've already made the payment, kindly ignore this message.
                                Thank you,
                                Vighnahar Agro"""
                                
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
                'interval_number': 1,  # 1440 minutes = 1 day, adjust this based on your needs
                'numbercall': -1,  # Infinite execution
                'nextcall': fields.Datetime.now(),
            })

    @api.model
    def init(self):
        """ Initialize method to create the cron job when the module is installed """
        super(CustomerInvoice, self).init()
        self.create_cron_job() 
        self.create_invoice_report_action()
      
    
            
            
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
    
   
    # def ensure_invoice_report_action(self):
    #     report_name = 'vighnahar_agro.report_invoice_custom'
    #     external_id = 'action_report_invoice_custom'

    #     Report = self.env['ir.actions.report'].sudo()
    #     existing = Report.search([('report_name', '=', report_name)], limit=1)

    #     if existing:
    #         _logger.info("Report action already exists: %s", existing.id)
    #         return existing

    #     new_action = Report.create({
    #         'name': 'Customer Invoice Report',
    #         'model': 'vighnahar_agro.customer_invoice',
    #         'report_type': 'qweb-pdf',
    #         'report_name': report_name,
    #         'print_report_name': "'Customer Invoice - %s' % (object.name)",
    #     })

    #     self.env['ir.model.data'].sudo().create({
    #         'name': external_id,
    #         'model': 'ir.actions.report',
    #         'module': 'vighnahar_agro',
    #         'res_id': new_action.id,
    #         'noupdate': True,
    #     })

    #     _logger.info("Manually created report action: %s", new_action.id)
    #     return new_action


class CustomerInvoiceLine(models.Model):
    _name = 'vighnahar_agro.customer_invoice_line'
    _description = 'Customer Invoice Line'

    customer_invoice_id = fields.Many2one('vighnahar_agro.customer_invoice', string='Invoice', ondelete='cascade')
    uom_category_id = fields.Many2one('vighnahar_agro.uom_category', related='product_id.category_id', string='UOM Category')
    product_category_id = fields.Many2one('vighnahar_agro.product_category', string='Product Category', domain="[('id', 'in', available_product_category_ids)]", ondelete='cascade')
    product_id = fields.Many2one('vighnahar_agro.product', string='Product', domain="[('product_category_id', '=', product_category_id), ('can_be_sold', '=', True)]", ondelete='cascade')
    
    quantity = fields.Float(string='Quantity', digits=(16, 4))
    uom_id = fields.Many2one('vighnahar_agro.uom', string='UOM', domain="[('category_id', '=', uom_category_id)]", ondelete='cascade')
    price = fields.Float(string='Unit Price', related='product_id.sales_price', store=True)
    total = fields.Float(string='Total Price', compute='_compute_total', store=True)
    converted_quantity = fields.Float(string='Converted Quantity', digits=(16, 4), compute='_compute_converted_quantity', store=True)
    converted_uom_id = fields.Many2one('vighnahar_agro.uom', string='Converted UOM', compute='_compute_converted_quantity', store=True, ondelete='cascade')
    available_product_category_ids = fields.Many2many('vighnahar_agro.product_category', compute='_compute_available_product_categories', relation='vighnahar_agro_prod_cat_invoice_line_rel')
    
    is_available = fields.Boolean(
        string='Is Available',
        compute='_compute_is_available',
        store=False,
        help="Indicates if the converted quantity is available in the warehouse."
    )
    
    # Field to select taxes
    tax_ids = fields.Many2many('vighnahar_agro.account_tax', string="Taxes", domain=[('active', '=', True)],
                               relation='vighnahar_agro_customer_invoice_line_account_tax_rel', ondelete='cascade')
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
    
    @api.onchange('product_id')
    def _onchange_set_uom_only(self):
        """ Just set the default UoM when a product is picked. """
        if self.product_id:
            # copy the product’s default UoM onto the line
            self.uom_id = self.product_id.uom_id
        else:
            # clear it if no product
            self.uom_id = False

            
  

class Payment(models.Model):
    _name = 'vighnahar_agro.payment'
    _description = 'Payment'
    _order = "id desc"

    name = fields.Char(string="Reference", default='New')
    customer_invoice_id = fields.Many2one('vighnahar_agro.customer_invoice', string='Customer Invoice', required=True, ondelete='cascade')
    party_id = fields.Many2one('vighnahar_agro.party', string="Party", required=True, domain=[('is_customer', '=', True)], ondelete='cascade')
    date = fields.Date(string="Date", default=fields.Date.today)
    invoice_type = fields.Selection([('regular', 'Regular Invoice'), ('percentage', 'Downpayment(Percentage)'), ('fixed_amount', 'Downpayment(Fixed Amount)')], string='Invoice Type', default='regular')
    amount = fields.Float(string='Amount', compute='_compute_amount', store=True)
    state = fields.Selection([('pending', 'Pending'), ('paid', 'Paid')], string='Status', default='pending', required=True)
    warehouse_id = fields.Many2one('vighnahar_agro.warehouse', string = "Warehouse", required=True, ondelete='cascade')
    payment_line_ids = fields.One2many('vighnahar_agro.payment_line', 'payment_id', string='Payment Lines', ondelete='cascade')

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

    payment_id = fields.Many2one('vighnahar_agro.payment', string='Payment', ondelete='cascade')
    product_id = fields.Many2one('vighnahar_agro.product', string='Product', ondelete='cascade')
    quantity = fields.Float(string='Quantity', digits=(16, 4))
    uom_id = fields.Many2one('vighnahar_agro.uom', string='UOM', ondelete='cascade')
    price = fields.Float(string='Unit Price')
    total = fields.Float(string='Total Price', compute='_compute_total', store=True)
    converted_quantity = fields.Float(string='Converted Quantity', digits=(16, 4), store=True)
    converted_uom_id = fields.Many2one('vighnahar_agro.uom', string='Converted UOM', ondelete='cascade')
    uom_category_id = fields.Many2one('vighnahar_agro.uom_category', string='UOM Category', ondelete='cascade')
    available_product_category_ids = fields.Many2many('vighnahar_agro.product_category', string='Available Product Categories')

    @api.depends('quantity', 'price')
    def _compute_total(self):
        for line in self:
            line.total = line.quantity * line.price
            


class DownpaymentWizard(models.TransientModel):
    _name = 'vighnahar_agro.downpayment_wizard'
    _description = 'Downpayment Wizard'

    customer_invoice_id = fields.Many2one('vighnahar_agro.customer_invoice', string='Customer Invoice', required=True, ondelete='cascade')
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
            
    @api.constrains('percentage', 'fixed_amount')
    def _check_downpayment_values(self):
        for wizard in self:
            if wizard.invoice_type == 'percentage':
                if wizard.percentage < 1:
                    raise ValidationError("Downpayment percentage must be at least 1%.")
                elif wizard.percentage > 100:
                    raise ValidationError("Downpayment percentage cannot exceed 100%. Please enter a valid amount.")
            elif wizard.invoice_type == 'fixed_amount':
                total = wizard.customer_invoice_id.total_amount
                if wizard.fixed_amount < 1:
                    raise ValidationError("Downpayment amount must be one or greater.")
                elif wizard.fixed_amount > total:
                    raise ValidationError("Downpayment amount cannot exceed the total invoice amount of ₹ {:.2f}.".format(total))

            
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
                'product_type': 'service',  # assuming it's  a service product
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
    