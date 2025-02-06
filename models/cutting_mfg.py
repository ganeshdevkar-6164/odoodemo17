from odoo import models, fields, api
from odoo.exceptions import UserError

# Define MfgCutting Model
class MfgCutting(models.Model):
    _name = 'mfg.cutting'
    _description = 'Manufacturing Cutting Process'

    name = fields.Char('Cutting Order', required=True, copy=False, readonly=True, default='New')

    state = fields.Selection(
        [('pending', 'Pending'),
         ('in_progress', 'In Progress'),
         ('completed', 'Completed')],
        default='pending',
        string='Status'
    )
    
    cutting_type = fields.Selection([
        ('three_cut', 'Three Cut'),
        ('four_cut', 'Four Cut'),
        ('grains', 'Grains'),
    ], string="Cutting Type", required=True)

    cutting_line_ids = fields.One2many('mfg.cutting.line', 'cutting_id', string="Cutting Lines")
    start_datetime = fields.Datetime(string='Start Date and Time', default=fields.Datetime.now, readonly=True)
    cutting_details_ids = fields.One2many('mfg.cutting.details', 'cutting_id', string="Cutting Details")

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('mfg.cutting.custom.sequence')
        return super().create(vals)

    def start_process(self):
        self.state = 'in_progress'
        for line in self.cutting_line_ids:
            product = line.product_id
            quantity_to_cut = line.available_quantity

            # Ensure there is enough quantity in AgroDehuskingSummary
            if product.total_dehusking_quantity >= quantity_to_cut:
                # Deduct quantity from AgroDehuskingSummary
                product.write({'total_dehusking_quantity': product.total_dehusking_quantity - quantity_to_cut})
            else:
                raise UserError(f"Not enough dehusking quantity for {product.name}.")

    def cancel_process(self):
        self.state = 'pending'

    def action_update(self):
        self.ensure_one()

        # Try to find an existing CuttingDetails record for this Cutting Order
        existing_details = self.env['mfg.cutting.details'].search([('name', '=', f'Cutting Details for {self.name}')], limit=1)

        # If an existing record is found, use it; otherwise, create a new one
        if existing_details:
            cutting_details = existing_details
        else:
            # Create MfgCuttingDetails for the cutting process
            cutting_details = self.env['mfg.cutting.details'].create({
                'name': f'Cutting Details for {self.name}',  # Set the name of the cutting details
                'cutting_id': self.id  # Set the cutting_id to the current mfg.cutting record
            })

            # For each MfgCuttingLine, create corresponding MfgCuttingDetailsLine
            for line in self.cutting_line_ids:
                # Ensure the line isn't already associated with a cutting details line
                existing_line = self.env['mfg.cutting.details.line'].search([
                    ('cutting_details_id', '=', cutting_details.id),
                    ('product_id', '=', line.product_id.id)
                ], limit=1)

                if not existing_line:
                    self.env['mfg.cutting.details.line'].create({
                        'cutting_details_id': cutting_details.id,
                        'product_id': line.product_id.id,
                        'available_quantity': line.available_quantity,
                        'uom_id': line.uom_id.id,
                        'remaining_quantity': line.available_quantity,  # Assuming remaining quantity starts as available
                    })

        # After creating/updating the details, automatically complete the parent Cutting Order if all details are 'done'
        if all(detail.state == 'done' for detail in cutting_details):
            self.state = 'completed'

        # Open the CuttingDetails form view (either existing or newly created)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cutting Process Details',
            'res_model': 'mfg.cutting.details',
            'res_id': cutting_details.id,
            'view_mode': 'form',
            'target': 'current',
        }

# Define MfgCuttingLine Model
class MfgCuttingLine(models.Model):
    _name = 'mfg.cutting.line'
    _description = 'Cutting Product Line'

    cutting_id = fields.Many2one('mfg.cutting', string='Cutting Order', required=True)
    product_id = fields.Many2one('agro.dehusking.summary', string="Dehusked Product", required=True)
    available_quantity = fields.Float('Available Quantity', required=True)
    uom_id = fields.Many2one('custom.uom', string="Unit of Measure", related='product_id.uom_id', store=True)

    @api.onchange('product_id')
    def _onchange_product_from_agro_dehusking_summary(self):
        if self.product_id:
            # Update available quantity from AgroDehuskingSummary
            self.available_quantity = self.product_id.total_dehusking_quantity
            self.uom_id = self.product_id.uom_id

# Define MfgCuttingDetails Model
class MfgCuttingDetails(models.Model):
    _name = 'mfg.cutting.details'
    _description = 'Cutting Process Details'

    name = fields.Char('Cutting Details', required=True)
    cutting_id = fields.Many2one('mfg.cutting', string="Cutting Order", required=True)
    cutting_details_line_ids = fields.One2many('mfg.cutting.details.line', 'cutting_details_id', string="Cutting Details Lines")
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft', string='Status')

    def action_confirm(self):
        """ Confirm the cutting details and automatically complete the cutting process if all details are confirmed. """
        
        # Set the state of the current CuttingDetails to 'done'
        self.state = 'done'

        # If all CuttingDetails are done, complete the Cutting process
        if all(detail.state == 'done' for detail in self.cutting_id.cutting_details_ids):
            self.cutting_id.state = 'completed'

        # Update the summary after the cutting process is completed
        self._update_cutting_summary()

    def _update_cutting_summary(self):
        """ Update the cutting summary after cutting process is completed """
        # We only update the summary once the cutting process is completed
        for line in self.cutting_details_line_ids:
            product = line.product_id
            cutting_quantity = line.remaining_quantity
            waste_quantity = line.wastage_quantity

            # Get the cutting type from the cutting order
            cutting_type = self.cutting_id.cutting_type

            # Update the summary for the product (only once after cutting)
            self.env['mfg.cutting.summary'].update_or_create_summary(
                product=product,
                cutting_quantity=cutting_quantity,
                waste_quantity=waste_quantity,
                cutting_type=cutting_type  # Pass cutting type to the summary update method
            )


class MfgCuttingDetailsLine(models.Model):
    _name = 'mfg.cutting.details.line'
    _description = 'Cutting Details Line'

    cutting_details_id = fields.Many2one('mfg.cutting.details', string="Cutting Details", required=True)
    product_id = fields.Many2one('agro.dehusking.summary', string="Product", store=True)
    available_quantity = fields.Float('Available Quantity', store=True)
    uom_id = fields.Many2one('custom.uom', string="UOM", store=True)
    remaining_quantity = fields.Float('Remaining Quantity')
    wastage_quantity = fields.Float('Waste Quantity', compute='_compute_wastage_quantity', store=True)

    @api.depends('available_quantity', 'remaining_quantity')
    def _compute_wastage_quantity(self):
        for record in self:
            record.wastage_quantity = record.available_quantity - record.remaining_quantity


class MfgCuttingSummary(models.Model):
    _name = 'mfg.cutting.summary'
    _description = 'Aggregated Cutting and Waste Stock per Product'
    _rec_name = 'product_id'

    product_id = fields.Many2one('agro.dehusking.summary', string="Product", required=True)
    cutting_type = fields.Selection([
        ('three_cut', 'Three Cut'),
        ('four_cut', 'Four Cut'),
        ('grains', 'Grains'),
    ], string="Cutting Type", required=True)
    total_cutting_quantity = fields.Float('Total Cutting Stock')
    total_waste_quantity = fields.Float('Total Waste Stock')
    uom_id = fields.Many2one('custom.uom', related='product_id.uom_id', string="Unit of Measure", readonly=True)

    @api.model
    def update_or_create_summary(self, product, cutting_quantity, waste_quantity, cutting_type):
        """ Update or create a summary record for a product based on cutting type """
        summary = self.search([
            ('product_id', '=', product.id),
            ('cutting_type', '=', cutting_type)
        ], limit=1)

        if summary:
            # Update the existing summary record by adding new quantities
            summary.total_cutting_quantity += cutting_quantity
            summary.total_waste_quantity += waste_quantity
        else:
            # Create a new summary record if none exists for the product and cutting type
            self.create({
                'product_id': product.id,
                'cutting_type': cutting_type,
                'total_cutting_quantity': cutting_quantity,
                'total_waste_quantity': waste_quantity,
            })
