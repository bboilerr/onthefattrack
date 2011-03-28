from django.utils import simplejson as json

def index():
    if len(request.args) != 1:
        redirect(URL('default', 'index'))
    else:
        slug = request.args[0]
    
        rows = db(db.auth_user.slug==slug).select()

        if (len(rows) != 1):
            redirect(URL('default', 'index'))
        else:
            response_dict = dict()

            row = rows[0]

            response_dict['name'] = row.first_name + ' ' + row.last_name

            weight_rows = db(db.weight.user_id==row.id).select()

            if (len(weight_rows) < 2):
                response_dict['error_message'] = 'Not enough data points to display a graph.'
            else:
                weights = map(lambda x: x.weight, weight_rows)
                tooltips = map(lambda x: "%0.1f" % x.weight, weight_rows)
                labels = map(lambda x: x.date.strftime('%m.%d.%y'), weight_rows)

                response_dict['data'] = json.dumps(weights)
                response_dict['tooltips'] = json.dumps(tooltips)
                response_dict['labels'] = json.dumps(labels)

            return response_dict

