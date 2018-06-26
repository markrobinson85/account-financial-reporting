# -*- coding: utf-8 -*-
# Copyright 2017 Eficent Business and IT Consulting Services S.L.
#   (http://www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

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
                                        default=False)

    partner_id = fields.Many2one('res.partner', 'Partner Account')

    statement_type = fields.Selection([('customer_outstanding_statement.statement', 'Oustanding Statement'),
                                       ('customer_activity_statement.statement', 'Activity Statement')],
                                      'Statement Type',
                                      default='customer_outstanding_statement.statement')

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

        result['partner_id'] = result.get('partner_id', self._context.get('active_id'))

        return result

    #     # v6.1 compatibility mode
    #     result['composition_mode'] = result.get('composition_mode', self._context.get('mail.compose.message.mode', 'comment'))
    #     result['model'] = result.get('model', self._context.get('active_model'))
    #     result['parent_id'] = result.get('parent_id', self._context.get('message_id'))
    #     if 'no_auto_thread' not in result and (not result['model'] or not result['model'] in self.pool or not hasattr(self.env[result['model']], 'message_post')):
    #         result['no_auto_thread'] = True
    #
    #     # default values according to composition mode - NOTE: reply is deprecated, fall back on comment
    #     if result['composition_mode'] == 'reply':
    #         result['composition_mode'] = 'comment'
    #     vals = {}
    #     if 'active_domain' in self._context:  # not context.get() because we want to keep global [] domains
    #         vals['use_active_domain'] = True
    #         vals['active_domain'] = '%s' % self._context.get('active_domain')
    #     if result['composition_mode'] == 'comment':
    #         vals.update(self.get_record_data(result))
    #
    #     for field in vals:
    #         if field in fields:
    #             result[field] = vals[field]
    #
    #     # TDE HACK: as mailboxes used default_model='res.users' and default_res_id=uid
    #     # (because of lack of an accessible pid), creating a message on its own
    #     # profile may crash (res_users does not allow writing on it)
    #     # Posting on its own profile works (res_users redirect to res_partner)
    #     # but when creating the mail.message to create the mail.compose.message
    #     # access rights issues may rise
    #     # We therefore directly change the model and res_id
    #     if result['model'] == 'res.users' and result['res_id'] == self._uid:
    #         result['model'] = 'res.partner'
    #         result['res_id'] = self.env.user.partner_id.id
    #
    #     if fields is not None:
    #         [result.pop(field, None) for field in result.keys() if field not in fields]
    #     return result

    @api.multi
    def action_compose_mail(self):
        """ Open a window to compose an email
        """

        self.ensure_one()

        if self.statement_type == 'customer_outstanding_statement.statement':
            template = self.env.ref('partner_statement_email.email_template_outstanding_statement', False)
        else:
            template = self.env.ref('partner_statement_email.email_template_activity_statement', False)

        compose_form = self.env.ref('partner_statement_email.email_compose_message_statement_wizard_form', False)
        ctx = dict(
            default_model='res.partner',
            default_res_id=self.partner_id.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            default_statement_type=self.statement_type,
            date_start=self.date_start,
            default_partner_to=self.partner_id.id,
            date_end=self.date_end,
            recipient_partner_ids=self.recipient_partner_ids.ids,
            show_aging_buckets=self.show_aging_buckets,
            statement_type=self.statement_type,
            mark_invoice_as_sent=True,
        )

        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message.statement',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

