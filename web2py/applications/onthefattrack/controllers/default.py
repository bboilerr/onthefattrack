# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is a samples controller
## - index is the default action of any application
## - user is required for authentication and authorization
## - download is for downloading files uploaded in the db (does streaming)
## - call exposes all registered services (none by default)
#########################################################################

def index():
    """
    example action using the internationalization operator T and flash
    rendered by views/default/index.html or views/generic.html
    """
    if (auth.user_id):
        redirect(URL('onthefattrack', 'page', 'index', args=(auth.user.slug,)))
    else:
        redirect(URL('onthefattrack', 'default', 'user', args=('login',)))

    return dict()

def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """
    return dict(form=auth())


def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request,db)


def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    session.forget()
    return service()

def blank():
    return dict()

@auth.requires_login()
def profile():
    """
    override auth profile
    """
    response_dict = dict()
    response_dict['user'] = auth.user

    return response_dict

def user_form():
    response_dict = dict()

    if not auth.user_id:
        redirect(URL('onthefattrack', 'default', 'blank'))
    else:
        crud.messages.submit_button='Save User'
        auth_user_form = crud.update(db.auth_user, auth.user_id, message='User Saved', deletable=False)

        auth.user = db(db.auth_user.id == auth.user_id).select().first()

        response_dict['url'] = '%s%s' % (BASE_URL, URL('onthefattrack', 'page', 'index', args=(auth.user.slug,)))
        response_dict['auth_user_form'] = auth_user_form

    return response_dict

def profile_form():
    response_dict = dict()

    if not auth.user_id:
        redirect(URL('onthefattrack', 'default', 'blank'))
    else:
        crud.messages.submit_button='Save User Profile'
        user_profile_form = crud.update(db.user_profile, auth.user.get_user_profile().id, message='User Profile Saved', deletable=False)

        response_dict['user_profile_form'] = user_profile_form

    return response_dict
