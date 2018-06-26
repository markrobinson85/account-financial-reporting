# -*- coding: utf-8 -*-

import base64
import re

from openerp import _, api, fields, models, SUPERUSER_ID
from openerp import tools
from openerp.tools.safe_eval import safe_eval as eval


# main mako-like expression pattern
EXPRESSION_PATTERN = re.compile('(\$\{.+?\})')


def _reopen(self, res_id, model, context=None):
    # save original model in context, because selecting the list of available
    # templates requires a model in context
    context = dict(context or {}, default_model=model)
    return {'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': res_id,
            'res_model': self._name,
            'target': 'new',
            'context': context,
            }


class MailComposer(models.TransientModel):
    """ Generic message composition wizard. You may inherit from this wizard
        at model and view levels to provide specific features.

        The behavior of the wizard depends on the composition_mode field:
        - 'comment': post on a record. The wizard is pre-populated via ``get_record_data``
        - 'mass_mail': wizard in mass mailing mode where the mail details can
            contain template placeholders that will be merged with actual data
            before being sent to each recipient.
    """
    _name = 'mail.compose.message.statement'
    _inherit = 'mail.compose.message'
    _description = 'Email composition wizard'

    # @api.model
    # def default_get(self, fields):
    #     """ Handle composition mode. Some details about context keys:
    #         - comment: default mode, model and ID of a record the user comments
    #             - default_model or active_model
    #             - default_res_id or active_id
    #         - reply: active_id of a message the user replies to
    #             - default_parent_id or message_id or active_id: ID of the
    #                 mail.message we reply to
    #             - message.res_model or default_model
    #             - message.res_id or default_res_id
    #         - mass_mail: model and IDs of records the user mass-mails
    #             - active_ids: record IDs
    #             - default_model or active_model
    #     """
    #     result = super(MailComposer, self).default_get(fields)
    #
    #     # v6.1 compatibility mode
    #     result['composition_mode'] = result.get('composition_mode', self._context.get('mail.compose.message.mode', 'comment'))
    #     result['model'] = result.get('model', self._context.get('active_model'))
    #     result['res_id'] = result.get('res_id', self._context.get('active_id'))
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

    # @api.model
    # def _get_composition_mode_selection(self):
    #     return [('comment', 'Post on a document'),
    #             ('mass_mail', 'Email Mass Mailing'),
    #             ('mass_post', 'Post on Multiple Documents')]

    # composition_mode = fields.Selection(selection=_get_composition_mode_selection, string='Composition mode', default='comment')
    # partner_ids = fields.Many2many(
    #     'res.partner', 'mail_compose_message_res_partner_rel',
    #     'wizard_id', 'partner_id', 'Additional Contacts')
    # use_active_domain = fields.Boolean('Use active domain')
    # active_domain = fields.Text('Active domain', readonly=True)
    # attachment_ids = fields.Many2many(
    #     'ir.attachment', 'mail_compose_message_ir_attachments_rel',
    #     'wizard_id', 'attachment_id', 'Attachments')
    # is_log = fields.Boolean('Log an Internal Note',
    #                         help='Whether the message is an internal note (comment mode only)')
    # subject = fields.Char(default=False)
    # # mass mode options
    # notify = fields.Boolean('Notify followers', help='Notify followers of the document (mass post only)')
    # template_id = fields.Many2one(
    #     'mail.template', 'Use template', index=True,
    #     domain="[('model', '=', model)]")

    # @api.multi
    # def check_access_rule(self, operation):
    #     """ Access rules of mail.compose.message:
    #         - create: if
    #             - model, no res_id, I create a message in mass mail mode
    #         - then: fall back on mail.message acces rules
    #     """
    #     # Author condition (CREATE (mass_mail))
    #     if operation == 'create' and self._uid != SUPERUSER_ID:
    #         # read mail_compose_message.ids to have their values
    #         message_values = {}
    #         self._cr.execute('SELECT DISTINCT id, model, res_id FROM "%s" WHERE id = ANY (%%s) AND res_id = 0' % self._table, (self.ids,))
    #         for mid, rmod, rid in self._cr.fetchall():
    #             message_values[mid] = {'model': rmod, 'res_id': rid}
    #         # remove from the set to check the ids that mail_compose_message accepts
    #         author_ids = [mid for mid, message in message_values.iteritems()
    #                       if message.get('model') and not message.get('res_id')]
    #         self = self.browse(list(set(self.ids) - set(author_ids)))  # not sure slef = ...
    #
    #     return super(MailComposer, self).check_access_rule(operation)

    @api.multi
    def _notify(self, force_send=False, user_signature=True):
        """ Override specific notify method of mail.message, because we do
            not want that feature in the wizard. """
        return

    @api.model
    def get_record_data(self, values):
        """ Returns a defaults-like dict with initial values for the composition
        wizard when sending an email related a previous email (parent_id) or
        a document (model, res_id). This is based on previously computed default
        values. """
        result, subject = {}, False
        if values.get('parent_id'):
            parent = self.env['mail.message'].browse(values.get('parent_id'))
            result['record_name'] = parent.record_name,
            subject = tools.ustr(parent.subject or parent.record_name or '')
            if not values.get('model'):
                result['model'] = parent.model
            if not values.get('res_id'):
                result['res_id'] = parent.res_id
            partner_ids = values.get('partner_ids', list()) + [(4, id) for id in parent.partner_ids.ids]
            if self._context.get('is_private') and parent.author_id:  # check message is private then add author also in partner list.
                partner_ids += [(4, parent.author_id.id)]
            result['partner_ids'] = partner_ids
        elif values.get('model') and values.get('res_id'):
            doc_name_get = self.env[values.get('model')].browse(values.get('res_id')).name_get()
            result['record_name'] = doc_name_get and doc_name_get[0][1] or ''
            subject = tools.ustr(result['record_name'])

        re_prefix = _('Re:')
        if subject and not (subject.startswith('Re:') or subject.startswith(re_prefix)):
            subject = "%s %s" % (re_prefix, subject)
        result['subject'] = subject

        partner_id = self.env[self._context.get('default_model')].browse(self._context.get('default_res_id'))

        data = {
            'date_end': self._context.get('date_end'),
            # 'statement_type': self._context.get('statement_type'),
            'company_id': partner_id.company_id.id,
            'partner_ids': partner_id.ids,
            # 'partner_to': partner_id.ids + self._context.get('recipient_partner_ids'),
            'show_aging_buckets': self._context.get('show_aging_buckets'),
            'filter_non_due_partners': False,
        }

        pdf = self.env['report'].get_pdf(
                                            partner_id,
                                            self._context.get('statement_type'),
                                            # html=html,
                                            data=data,
                                            # context=self._context
                                        )

        attachment_id = self.env['ir.attachment'].create({
            'name': 'Customer Statement',
            'type': 'binary',
            'datas': base64.encodestring(pdf),
            'datas_fname': 'customer_statement.pdf',
            # 'res_model': 'res.partner',
            # 'res_id': partner_id.id,
            'mimetype': 'application/pdf'
        })

        result['attachment_ids'] = [attachment_id.id]
        result['partner_ids'] = partner_id.ids + self._context.get('recipient_partner_ids')
        result['partner_to'] = partner_id.ids + self._context.get('recipient_partner_ids')
        return result

    #------------------------------------------------------
    # Wizard validation and send
    #------------------------------------------------------
    # action buttons call with positionnal arguments only, so we need an intermediary function
    # to ensure the context is passed correctly

    # @api.multi
    # def send_mail_action(self):
    #     # TDE/ ???
    #     return self.send_mail()
    #
    # @api.multi
    # def send_mail(self, auto_commit=False):
    #     """ Process the wizard content and proceed with sending the related
    #         email(s), rendering any template patterns on the fly if needed. """
    #     for wizard in self:
    #         # Duplicate attachments linked to the email.template.
    #         # Indeed, basic mail.compose.message wizard duplicates attachments in mass
    #         # mailing mode. But in 'single post' mode, attachments of an email template
    #         # also have to be duplicated to avoid changing their ownership.
    #         if wizard.attachment_ids and wizard.composition_mode != 'mass_mail' and wizard.template_id:
    #             new_attachment_ids = []
    #             for attachment in wizard.attachment_ids:
    #                 if attachment in wizard.template_id.attachment_ids:
    #                     new_attachment_ids.append(attachment.copy({'res_model': 'mail.compose.message', 'res_id': wizard.id}).id)
    #                 else:
    #                     new_attachment_ids.append(attachment.id)
    #                 wizard.write({'attachment_ids': [(6, 0, new_attachment_ids)]})
    #
    #         # Mass Mailing
    #         mass_mode = wizard.composition_mode in ('mass_mail', 'mass_post')
    #
    #         Mail = self.env['mail.mail']
    #         ActiveModel = self.env[wizard.model if wizard.model else 'mail.thread']
    #         if wizard.template_id:
    #             # template user_signature is added when generating body_html
    #             # mass mailing: use template auto_delete value -> note, for emails mass mailing only
    #             Mail = Mail.with_context(mail_notify_user_signature=False)
    #             ActiveModel = ActiveModel.with_context(mail_notify_user_signature=False, mail_auto_delete=wizard.template_id.auto_delete)
    #         if not hasattr(ActiveModel, 'message_post'):
    #             ActiveModel = self.env['mail.thread'].with_context(thread_model=wizard.model)
    #         if wizard.composition_mode == 'mass_post':
    #             # do not send emails directly but use the queue instead
    #             # add context key to avoid subscribing the author
    #             ActiveModel = ActiveModel.with_context(mail_notify_force_send=False, mail_create_nosubscribe=True)
    #         # wizard works in batch mode: [res_id] or active_ids or active_domain
    #         if mass_mode and wizard.use_active_domain and wizard.model:
    #             res_ids = self.env[wizard.model].search(eval(wizard.active_domain)).ids
    #         elif mass_mode and wizard.model and self._context.get('active_ids'):
    #             res_ids = self._context['active_ids']
    #         else:
    #             res_ids = [wizard.res_id]
    #
    #         batch_size = int(self.env['ir.config_parameter'].sudo().get_param('mail.batch_size')) or self._batch_size
    #         sliced_res_ids = [res_ids[i:i + batch_size] for i in range(0, len(res_ids), batch_size)]
    #
    #         for res_ids in sliced_res_ids:
    #             batch_mails = Mail
    #             all_mail_values = wizard.get_mail_values(res_ids)
    #             for res_id, mail_values in all_mail_values.iteritems():
    #                 if wizard.composition_mode == 'mass_mail':
    #                     batch_mails |= Mail.create(mail_values)
    #                 else:
    #                     subtype = 'mail.mt_comment'
    #                     if wizard.is_log or (wizard.composition_mode == 'mass_post' and not wizard.notify):  # log a note: subtype is False
    #                         subtype = False
    #                     ActiveModel.browse(res_id).message_post(message_type='comment', subtype=subtype, **mail_values)
    #
    #             if wizard.composition_mode == 'mass_mail':
    #                 batch_mails.send(auto_commit=auto_commit)
    #
    #     return {'type': 'ir.actions.act_window_close'}


    # Override mail_values and add configured attachments.
    @api.multi
    def get_mail_values(self, res_ids):
        """Generate the values that will be used
           by send_mail to create mail_messages
           or mail_mails. """

        self.ensure_one()
        results = self.get_mail_values(res_ids)

        data = {
            'date_end': self._context.get('date_end'),
            'company_id': self._context.get('statement_type'),
            'partner_ids': self._context.get('active_ids'),
            'show_aging_buckets': self._context.get('show_aging_buckets'),
            'filter_non_due_partners': False,
        }

        attachment_id = self.env['report'].with_context(landscape=True).get_action(self, self._context.get('statement_type') + '.statement', data=data)

        for res in results:
            res['attachment_ids'] = [attachment_id.id]

        return results

