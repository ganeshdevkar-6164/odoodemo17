from odoo import models, fields, api
from odoo.exceptions import UserError

# Define AgroDehusking Model
class AgroDehusking(models.Model):
    _name = 'agro.dehusking'
    _description = 'Agro Dehusking Process'

    name = fields.Char('Dehusking', required=True, copy=False, readonly=True, default='New')

    state = fields.Selection(
        [('pending', 'Pending'),
         ('in_progress', 'In Progress'),
         ('completed', 'Completed')],
        default='pending',
        string='Status'
    )
    dehusking_line_ids = fields.One2many('agro.dehusking.line', 'dehusking_id', string="Dehusking Products")
    start_datetime = fields.Datetime(string='Start Date and Time', default=fields.Datetime.now, readonly=True)
    dehusking_details_ids = fields.One2many('agro.dehusking.details', 'dehusking_id', string="Dehusking Details")

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('agro.dehusking.custom.sequence')
        return super().create(vals)

    def start_process(self):
        self.state = 'in_progress'
        for line in self.dehusking_line_ids:
            product = line.product_id
            quantity_to_deduct = line.available_quantity
            if product.quantity >= quantity_to_deduct:
                product.write({'quantity': product.quantity - quantity_to_deduct})
            else:
                raise UserError(f"Not enough quantity for {product.name} in sub-inventory")

    def cancel_process(self):
        self.state = 'pending'

    def action_update(self):
        self.ensure_one()

        # Try to find an existing AgroDehuskingDetails record for this Dehusking Order
        existing_details = self.env['agro.dehusking.details'].search([('name', '=', f'Dehusking Details for {self.name}')], limit=1)

        # If an existing record is found, use it; otherwise, create a new one
        if existing_details:
            dehusking_details = existing_details
        else:
            # Create AgroDehuskingDetails for the dehusking process
            dehusking_details = self.env['agro.dehusking.details'].create({
                'name': f'Dehusking Details for {self.name}',  # Set the name of the dehusking details
                'dehusking_id': self.id  # Set the dehusking_id to the current agro.dehusking record
            })

            # For each AgroDehuskingLine, create corresponding AgroDehuskingDetailsLine
            for line in self.dehusking_line_ids:
                self.env['agro.dehusking.details.line'].create({
                    'dehusking_details_id': dehusking_details.id,
                    'product_id': line.product_id.id,
                    'available_quantity': line.available_quantity,
                    'uom_id': line.uom_id.id,
                    'remaining_quantity': line.available_quantity,  # Assuming remaining quantity starts as available
                })

        # After creating/updating the details, automatically complete the parent AgroDehusking if any detail is 'done'
        if all(detail.state == 'done' for detail in dehusking_details):
            self.state = 'completed'

        # Open the AgroDehuskingDetails form view (either existing or newly created)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dehusking Process Details',
            'res_model': 'agro.dehusking.details',
            'res_id': dehusking_details.id,
            'view_mode': 'form',
            'target': 'current',
        }

# Define AgroDehuskingDetails Model
class AgroDehuskingDetails(models.Model):
    _name = 'agro.dehusking.details'
    _description = 'Dehusking Process Details'

    name = fields.Char('Dehusking details', required=True)
    dehusking_id = fields.Many2one('agro.dehusking', string="Dehusking Order", required=True)
    dehusking_details_line_ids = fields.One2many('agro.dehusking.details.line', 'dehusking_details_id', string="Dehusking Details Lines")
    state = fields.Selection(
        [('draft', 'Draft'),
         ('done', 'Done')],
        default='draft',
        string='Status'
    )

    def action_confirm(self):
        """ Confirm the dehusking details and automatically complete the dehusking process if all details are confirmed. """
        
        # Set the state of the current AgroDehuskingDetails to 'done'
        self.state = 'done'

        # If all AgroDehuskingDetails are done, complete the AgroDehusking process
        if all(detail.state == 'done' for detail in self.dehusking_id.dehusking_details_ids):
            self.dehusking_id.state = 'completed'
        
        self._update_summary_after_dehusking()

    def _update_summary_after_dehusking(self):
        """ Update the summary after the dehusking process is completed """
        # We only update the summary once the dehusking is completed
        for detail in self.dehusking_details_line_ids:  # Use dehusking_details_line_ids here
            product = detail.product_id
            dehusking_quantity = detail.remaining_quantity
            waste_quantity = detail.wastage_quantity

            # Update the summary for the product (only once after dehusking)
            self.env['agro.dehusking.summary'].update_or_create_summary(
                product=product,
                dehusking_quantity=dehusking_quantity,
                waste_quantity=waste_quantity
            )

# Define AgroDehuskingLine Model
class AgroDehuskingLine(models.Model):
    _name = 'agro.dehusking.line'
    _description = 'Dehusking Product Line'

    dehusking_id = fields.Many2one('agro.dehusking', string='Dehusking Order', required=True)
    product_id = fields.Many2one('sub.inventory', string="Product", required=True)
    available_quantity = fields.Float('Available Quantity', required=True)
    uom_id = fields.Many2one('custom.uom', string="Unit of Measure", related='product_id.uom_id', store=True)

    @api.onchange('product_id')
    def _onchange_product_from_sub_inventory(self):
        if self.product_id:
            self.available_quantity = self.product_id.quantity
            self.uom_id = self.product_id.uom_id


# Define AgroDehuskingDetailsLine Model
class AgroDehuskingDetailsLine(models.Model):
    _name = 'agro.dehusking.details.line'
    _description = 'Dehusking Details Line'

    dehusking_details_id = fields.Many2one('agro.dehusking.details', string="Dehusking Details", required=True)
    product_id = fields.Many2one('sub.inventory', string="Product", store=True)
    available_quantity = fields.Float('Available Quantity', store=True)
    uom_id = fields.Many2one('custom.uom', string="UOM", store=True)
    remaining_quantity = fields.Float('Remaining Quantity')
    wastage_quantity = fields.Float('Waste Quantity', compute='_compute_wastage_quantity', store=True)

    @api.depends('available_quantity', 'remaining_quantity')
    def _compute_wastage_quantity(self):
        for record in self:
            # Compute wastage as the difference between available and remaining quantities
            record.wastage_quantity = record.available_quantity - record.remaining_quantity


# Define AgroDehuskingSummary Model
class AgroDehuskingSummary(models.Model):
    _name = 'agro.dehusking.summary'
    _description = 'Aggregated Dehusking and Waste Stock per Product'
    _rec_name='product_id'

    product_id = fields.Many2one('sub.inventory', string="Product", required=True)
    total_dehusking_quantity = fields.Float('Total Dehusking Stock')
    total_waste_quantity = fields.Float('Total Waste Stock')
    uom_id = fields.Many2one('custom.uom', related='product_id.uom_id', string="Unit of Measure", readonly=True)

    @api.model
    def update_or_create_summary(self, product, dehusking_quantity, waste_quantity):
        """ Update or create a summary record for a product """
        summary = self.search([('product_id', '=', product.id)], limit=1)

        if summary:
            # Update the existing summary record by adding new quantities
            summary.total_dehusking_quantity += dehusking_quantity
            summary.total_waste_quantity += waste_quantity
        else:
            # Create a new summary record if none exists for the product
            self.create({
                'product_id': product.id,
                'total_dehusking_quantity': dehusking_quantity,
                'total_waste_quantity': waste_quantity,
            })
