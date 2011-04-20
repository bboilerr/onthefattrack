from gluon.contrib import simplejson as json

def index():
    if len(request.args) != 1:
        redirect(URL('default', 'index'))

    slug = request.args[0]

    rows = db(db.auth_user.slug==slug).select()

    if (len(rows) != 1):
        redirect(URL('default', 'index'))

    response_dict = dict()

    user = rows.first()
    response_dict['user'] = user

    user_unit = user.get_user_profile.weight_unit

    response_dict['weight_unit'] = user_unit

    weight_rows = db(db.weight.user_id==user.id).select()
    weight_rows = weight_rows.sort(lambda row : row.timestamp).sort(lambda row : row.date)
    num_weight_rows = len(weight_rows)
    response_dict['data_length'] = num_weight_rows

    if (num_weight_rows < 2):
        response_dict['error_message'] = 'Not enough data points to display a graph.'
        response_dict['weight_rows'] = weight_rows
    else:
        weights = map(lambda x: x.weight, weight_rows)
        tooltips = map(lambda x: "%s: %0.1f %s" % (x.date.strftime('%d %b %Y'), x.weight, user_unit), weight_rows)
        labels = map(lambda x: x.date.strftime('%d %b %Y'), weight_rows)

        response_dict['data'] = json.dumps(weights)
        response_dict['tooltips'] = json.dumps(tooltips)
        response_dict['labels'] = json.dumps(labels)

    return response_dict

def weight_form():
    response_dict = dict()
    if len(request.args) == 0:
        pass
    else:
        user_id = int(request.args[0])

        if (auth.user_id == user_id):
            form = crud.create(db.weight, message='Weight Added')
            response_dict['form'] = form

    return response_dict

def notify_post(form):
    post_id = form.vars.id
    rows = db(db.post.id==post_id).select()

    if len(rows):
        post = rows.first()

        if (post.author_id != post.page_id):
            page_user = post.get_page_user
            author = post.get_author

            email = page_user.email

            if email:
                response_dict = dict()
                response_dict['page_user'] = page_user
                response_dict['author'] = author
                response_dict['url'] = '%s%s' % (BASE_URL, URL('onthefattrack', 'page', 'post', args=(post.id,)))

                message = response.render('page/email/notify_post.html', response_dict) 

                mail.send(to=[email],
                        subject='New Post From %s' % (author.get_name,),
                        message=message)

def post_form():
    response_dict = dict()
    if len(request.args) == 0:
        pass
    else:
        user_id = int(request.args[0])

        if (auth.user_id):
            form = crud.create(db.post, message='Post Added', onaccept=lambda form: notify_post(form))
            form.insert(0, INPUT(_type='text', _hidden='true', _name='page_id', _value=user_id))

            user = db(db.auth_user.id == auth.user_id).select().first()
            form.insert(0, INPUT(_type='text', _hidden='true', _name='name', _value=user.get_name))
            form.insert(0, INPUT(_type='text', _hidden='true', _name='slug', _value=user.slug))

            response_dict['form'] = form

    return response_dict

def posts():
    response_dict = dict()
    if len(request.args) == 0:
        pass
    else:
        user_id = int(request.args[0])
        response_dict['user_id'] = user_id

        posts = db(db.post.page_id==user_id).select()
        posts = posts.sort(lambda r: r.date, reverse=True)
        response_dict['posts'] = posts

    return response_dict

def post():
    if len(request.args) != 1:
        redirect(URL('default', 'index'))

    post_id = int(request.args[0])

    post_rows = db(db.post.id==post_id).select()

    if (len(post_rows) != 1):
        redirect(URL('default', 'index'))

    response_dict = dict()

    post = post_rows.first()
    response_dict['post'] = post


    return response_dict

# Use this to get just the post HTML for AJAX
def ajaxpost():
    return post()
