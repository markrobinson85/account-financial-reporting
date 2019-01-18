# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
from datetime import date, timedelta
from openerp import api, fields, models, _


class CustomerOutstandingStatementWizard(models.TransientModel):
    """Customer Outstanding Statement wizard."""

    _name = 'partner.send.statement.wizard'
    _description = 'Partner Send Statement Wizard'

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.user.company_id,
        string='Company'
    )

    date_start = fields.Date(required=True,
                             string='Date Start',
                             default=fields.Date.to_string(
                                 date.today() - timedelta(days=120)))

    date_end = fields.Date(string='Date Ending', required=True,
                           default=fields.Date.to_string(date.today()))

    send_monthly = fields.Boolean('Send Monthly')

    # recipient_partner_ids = fields.One2many('res.partner', string='Recipients', store=False)
    recipient_partner_ids = fields.Many2many(
        'res.partner', 'partner_send_statement_res_partner_rel',
        'wizard_id', 'partner_id', 'Recipients')

    show_aging_buckets = fields.Boolean(string='Include Aging Buckets',
                                        default=True)

    partner_id = fields.Many2one('res.partner', 'Partner Account')

    statement_type = fields.Selection([('customer_outstanding_statement.statement', 'Oustanding Statement'),
                                       ('customer_activity_statement.statement', 'Activity Statement')],
                                      'Statement Type',
                                      default='customer_outstanding_statement.statement')

    subscription = fields.Boolean('Subscribe', help='Subscribe the customer to monthly e-mails')

    date_next_send = fields.Date('Scheduled Send Date', help='Select the date you want the next e-mail to send. \n\n'
                                                           'If you select Compose E-mail, the e-mail will send today, '
                                                           'and an e-mail will be scheduled for the next date selected. \n '
                                                           'If you select Schedule E-mail, no e-mail will be sent until '
                                                           'the scheduled date.')

    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    credit = fields.Monetary(string='Total Receivable', help="Total amount this customer owes you.",
                            currency_field='company_currency_id',
                            related='partner_id.credit',
                             )
    dont_send_when_zero = fields.Boolean('Skip sending when zero balance', default=True)

    @api.model
    def default_get(self, fields):
        """ Handle composition mode. Some details about context keys:
            - comment: default mode, model and ID of a record the user comments
                - default_model or active_model
                - default_res_id or active_id
            - reply: active_id of a message the user replies to
                - default_parent_id or message_id or active_id: ID of the
                    mail.message we reply to
                - message.res_model or default_model
                - message.res_id or default_res_id
            - mass_mail: model and IDs of records the user mass-mails
                - active_ids: record IDs
                - default_model or active_model
        """
        result = super(CustomerOutstandingStatementWizard, self).default_get(fields)

        partner_id = self.env['res.partner'].browse(self._context.get('active_id'))

        if partner_id.commercial_partner_id.id != partner_id.id:
            result['recipient_partner_ids'] = [partner_id.commercial_partner_id.id, partner_id.id]
            result['partner_id'] = partner_id.commercial_partner_id.id
        else:
            result['recipient_partner_ids'] = [partner_id.commercial_partner_id.id]
            result['partner_id'] = partner_id.commercial_partner_id.id

        return result

    @api.multi
    def _create_or_update(self):
        schedule_id = self.env['scheduler.partner.statement']

        schedule_id = schedule_id.search([('partner_id', '=', self.partner_id.commercial_partner_id.id)], limit=1)

        if schedule_id.id:
            schedule_id.write({
                'partner_id': self.partner_id.commercial_partner_id.id,
                'recipient_ids': [(6, 0, self.recipient_partner_ids.ids)],
                'statement_type': self.statement_type,
                'date_next_send': self.date_next_send or date.today(),
                'show_aging_buckets': self.show_aging_buckets,
                'company_id': self.partner_id.company_id.id,
                'user_id': self.env.user.id,
                'active': self.subscription,
                'dont_send_when_zero': self.dont_send_when_zero,
            })
        else:
            schedule_id = schedule_id.create({
                'partner_id': self.partner_id.commercial_partner_id.id,
                'recipient_ids': [(6, 0, self.recipient_partner_ids.ids)],
                'statement_type': self.statement_type,
                'date_next_send': self.date_next_send,
                'show_aging_buckets': self.show_aging_buckets,
                'company_id': self.partner_id.company_id.id,
                'user_id': self.env.user.id,
                'active': self.subscription,
                'dont_send_when_zero': self.dont_send_when_zero,
            })
        return schedule_id

    @api.multi
    def action_schedule_message(self):
        """ Open a window to compose an email
        """

        self.ensure_one()

        self._create_or_update()

        return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def action_compose_mail(self):
        '''
        This function opens a window to compose an email, with the statement template loaded by default
        '''
        self.ensure_one()

        if self.statement_type == 'customer_outstanding_statement.statement':
            template_id = self.env.ref('partner_statement_email.email_template_outstanding_statement', False)
        else:
            template_id = self.env.ref('partner_statement_email.email_template_activity_statement', False)

        try:
            compose_form_id = self.env.ref('mail.email_compose_message_wizard_form', False)
        except ValueError:
            compose_form_id = False

        schedule_id = self._create_or_update()

        data = {
            'date_end': self.date_end,
            'date_start': self.date_start,
            'company_id': self.partner_id.company_id.id,
            'partner_ids': self.partner_id.ids,
            'show_aging_buckets': self.show_aging_buckets,
            'filter_non_due_partners': False,
        }

        pdf = self.env['report'].get_pdf(
            schedule_id.partner_id,
            schedule_id.statement_type,
            data=data,
        )

        attachment_id = self.env['ir.attachment'].create({
            'name': 'Customer Statement - ' + str(date.today()) + '.pdf',
            'type': 'binary',
            'datas': base64.encodestring(pdf),
            'datas_fname': 'Customer Statement - ' + str(date.today()) + '.pdf',
            'mimetype': 'application/pdf'
        })

        ctx = dict(
            default_model='scheduler.partner.statement',
            default_res_id=schedule_id.id,
            default_use_template=bool(template_id),
            default_template_id=template_id and template_id.id or False,
            default_composition_mode='comment',
            default_attachment_ids=attachment_id.ids,
            default_partner_ids=self.recipient_partner_ids.ids,

        )

        if self.subscription:
            schedule_id = self.env['scheduler.partner.statement'].search([('partner_id', '=', self.partner_id.id)])
            if schedule_id.id:
                schedule_id.date_last_sent = date.today()
                schedule_id.set_thirty_days_later()

        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id.id, 'form')],
            'view_id': compose_form_id.id,
            'target': 'new',
            'context': ctx,
        }

        # return {
        #     'type': 'ir.actions.act_window',
        #     'view_type': 'form',
        #     'view_mode': 'form',
        #     'res_model': 'mail.compose.message',
        #     'views': [(compose_form_id.id, 'form')],
        #     'view_id': compose_form_id.id,
        #     'target': 'new',
        #     'context': ctx,
        # }
