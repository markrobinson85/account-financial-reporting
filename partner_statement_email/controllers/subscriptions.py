# -*- coding: utf-8 -*-

from openerp import http
from openerp.http import Response
import json
import dateutil.parser
import re


class SubscriptionManagement(http.Controller):

    @http.route('/subscribe/statement/<subscription_id>', type='http', auth='public', method='get')
    def po_search(self, subscription_id):
        # json_response = self._json_obj()
        if isinstance(subscription_id, basestring):
            # Sanitize/remove non-alphanumeric characters, except dashes
            # po_number = re.sub(r'\W+', '', po_number)
            # zip = re.sub(r'\W+', '', zip)
            subscription_id = re.sub(r'[^\w-]|_', '', subscription_id)

            subscription = http.request.env['scheduler.partner.statement'].sudo().browse(int(subscription_id))

            if len(subscription) > 0:
                # If nothing was found, try again but capitalize the input.
                subscription.active = False

                return Response("You have been unsubscribed.",
                                content_type='application/html;charset=utf-8',
                                status=200,
                                headers=[('Cache-Control', 'public, max-age: 3600')])

        return Response("Unable to find your subscription",
                        content_type='application/html+xml;charset=utf-8',
                        status=404,
                        headers=[('Cache-Control', 'public, max-age: 3600')])

