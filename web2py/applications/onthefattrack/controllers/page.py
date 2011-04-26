from gluon.contrib import simplejson as json

def index():
    if len(request.args) != 1:
        raise HTTP(404)

    slug = request.args[0]

    rows = db(db.auth_user.slug==slug).select()

    if (len(rows) != 1):
        raise HTTP(404)

    response_dict = dict()

    user = rows.first()
    response_dict['user'] = user

    user_unit = user.get_user_profile().weight_unit

    response_dict['weight_unit'] = user_unit

    weight_rows = user.weight.select()
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
        redirect(URL('onthefattrack', 'default', 'blank'))
    else:
        user_id = int(request.args[0])

        if (auth.user_id == user_id):
            crud.messages.submit_button='Add Weight'
            form = crud.create(db.weight, message='Weight Added')
            response_dict['form'] = form
        else:
            redirect(URL('onthefattrack', 'default', 'blank'))

    return response_dict

def notify_post(form):
    post_id = form.vars.id
    rows = db(db.post.id==post_id).select()

    if len(rows):
        post = rows.first()

        if (post.author_id != post.page_id):
            page_user = post.get_page_user()
            author = post.get_author()

            email = page_user.email

            if email:
                response_dict = dict()
                response_dict['page_user'] = page_user
                response_dict['author'] = author
                response_dict['url'] = '%s%s' % (BASE_URL, URL('onthefattrack', 'page', 'post', args=(post.id,)))
                response_dict['post'] = post
                subject = response_dict['subject'] = 'New Post From %s' % (author.get_name,)

                message_html = response.render('page/email/notify_post.html', response_dict) 
                message_txt = response.render('page/email/notify_post.txt', response_dict) 

                mail.send(to=[email],
                        subject=subject,
                        message=(message_txt, message_html))

def post_form():
    response_dict = dict()
    if len(request.args) == 0:
        redirect(URL('onthefattrack', 'default', 'blank'))
    else:
        user_id = int(request.args[0])

        if not auth.user_id:
            redirect(URL('onthefattrack', 'default', 'blank'))
        else:
            crud.messages.submit_button='Add Post'
            form = crud.create(db.post, message='Post Added', onaccept=lambda form: notify_post(form))
            form.insert(0, INPUT(_type='text', _hidden='true', _name='page_id', _value=user_id))

            response_dict['form'] = form

    return response_dict

def get_post_user_dict(posts):
    from sets import Set

    user_set = Set()

    for row in posts:
        user_set.add(row.author_id)
        user_set.add(row.page_id)

    users = db(db.auth_user.id.belongs(list(user_set))).select()

    user_dict = {}
    for user in users:
        user_dict[user.id] = user

    return user_dict

def get_post_comment_dict(posts):
    comment_dict = {}

    post_ids = [post.id for post in posts]

    comments = db(db.comment.post_id.belongs(post_ids)).select().sort(lambda c: c.date)

    comment_dict['user_dict'] = get_comment_user_dict(comments)

    for post in posts:
        comment_dict[post.id] = []

    for comment in comments:
        comment_dict[comment.post_id].append(comment)

    return comment_dict

def get_comment_user_dict(comments):
    from sets import Set

    user_set = Set([comment.author_id for comment in comments])

    users = db(db.auth_user.id.belongs(list(user_set))).select()

    user_dict = {}
    for user in users:
        user_dict[user.id] = user

    return user_dict


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

        response_dict['logged_in'] = bool(auth.user_id)
        response_dict['user_dict'] = get_post_user_dict(posts)
        response_dict['comment_dict'] = get_post_comment_dict(posts)

        response_dict

    return response_dict

def post():
    if len(request.args) != 1:
        raise HTTP(404)

    post_id = int(request.args[0])

    post_rows = db(db.post.id==post_id).select()

    if (len(post_rows) != 1):
        raise HTTP(404)

    response_dict = dict()

    post = post_rows.first()
    response_dict['post'] = post

    response_dict['logged_in'] = bool(auth.user_id)
    response_dict['user_dict'] = get_post_user_dict([post])
    response_dict['comment_dict'] = get_post_comment_dict([post])

    return response_dict

# Use this to get just the post HTML for AJAX
def ajaxpost():
    return post()

def notify_comment(form):
    comment_id = form.vars.id
    rows = db(db.comment.id==comment_id).select()

    if len(rows):
        comment = rows.first()

        author_id = comment.author_id
        author = comment.get_author()
        post = comment.get_post()

        # Get post author and page user
        from sets import Set
        user_ids_to_notify_set = Set([post.author_id, post.page_id])

        post_comments = post.comment.select()

        # Get authors for all post comments
        user_ids_to_notify_set.update([post_comment.author_id for post_comment in post_comments])

        # If those authors are not the author of this new comment, notify them
        user_ids_to_notify = filter(lambda user_id: user_id != author_id, list(user_ids_to_notify_set))

        if user_ids_to_notify:
            users_to_notify = db(db.auth_user.id.belongs(user_ids_to_notify)).select()

            for user in users_to_notify:
                email = user.email

                if email:
                    response_dict = dict()
                    response_dict['notify_user'] = user
                    response_dict['author'] = author
                    response_dict['url'] = '%s%s' % (BASE_URL, URL('onthefattrack', 'page', 'post', args=(post.id,)))
                    response_dict['comment'] = comment
                    subject = response_dict['subject'] = 'New comment From %s' % (author.get_name,)

                    message_html = response.render('page/email/notify_comment.html', response_dict) 
                    message_txt = response.render('page/email/notify_comment.txt', response_dict) 

                    mail.send(to=[email],
                            subject=subject,
                            message=(message_txt, message_html))

def comment_form():
    response_dict = dict()
    if len(request.args) == 0:
        redirect(URL('onthefattrack', 'default', 'blank'))
    else:
        post_id = int(request.args[0])

        if not auth.user_id:
            redirect(URL('onthefattrack', 'default', 'blank'))
        else:
            crud.messages.submit_button='Add Comment'
            form = crud.create(db.comment, message='Comment Added', onaccept=lambda form: notify_comment(form))
            form.insert(0, INPUT(_type='text', _hidden='true', _name='post_id', _value=post_id))

            response_dict['form'] = form

    return response_dict

def ajaxcomment():
    if len(request.args) != 1:
        redirect(URL('onthefattrack', 'default', 'blank'))

    comment_id = int(request.args[0])

    comment_rows = db(db.comment.id==comment_id).select()

    if (len(comment_rows) != 1):
        redirect(URL('onthefattrack', 'default', 'blank'))

    response_dict = dict()

    comment = comment_rows.first()
    response_dict['comment'] = comment

    response_dict['user_dict'] = get_comment_user_dict([comment])

    return response_dict
