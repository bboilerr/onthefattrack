from gluon.contrib import simplejson as json

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

            user_id = row.id
            response_dict['name'] = row.first_name + ' ' + row.last_name

            weight_rows = db(db.weight.user_id==user_id).select(
                    orderby=db.weight.date)

            if (len(weight_rows) < 2):
                response_dict['error_message'] = 'Not enough data points to display a graph.'
                response_dict['weight_table'] = crud.select(db.weight, db.weight.user_id==user_id)
            else:
                weights = map(lambda x: x.weight, weight_rows)
                tooltips = map(lambda x: "%s: %0.1f lbs." % (x.date.strftime('%d%b%y'), x.weight), weight_rows)
                labels = map(lambda x: x.date.strftime('%d%b%y'), weight_rows)

                response_dict['data'] = json.dumps(weights)
                response_dict['tooltips'] = json.dumps(tooltips)
                response_dict['labels'] = json.dumps(labels)

            if auth.user_id == user_id:
                crud.messages.record_created = 'Weight Added'
                form = crud.create(db.weight, next=URL('index/%s' % slug),
                        message='Weight Added')

                response_dict['form'] = form

            return response_dict

@auth.requires_login()
def weight_form():
    response_dict = dict()

    form = crud.create(db.weight)
    response_dict['form'] = form

    return response_dict


