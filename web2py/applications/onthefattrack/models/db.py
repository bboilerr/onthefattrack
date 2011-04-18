# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This scaffolding model makes your app work on Google App Engine too
#########################################################################

if request.env.web2py_runtime_gae:            # if running on Google App Engine
    db = DAL('gae')                           # connect to Google BigTable
                                              # optional DAL('gae://namespace')
    session.connect(request, response, db = db) # and store sessions and tickets there
    ### or use the following lines to store sessions in Memcache
    # from gluon.contrib.memdb import MEMDB
    # from google.appengine.api.memcache import Client
    # session.connect(request, response, db = MEMDB(Client()))
else:                                         # else use a normal relational database
    db = DAL('sqlite://storage.sqlite')       # if not, use SQLite or other DB
## if no need for session
# session.forget()

#########################################################################
## Here is sample code if you need for
## - email capabilities
## - authentication (registration, login, logout, ... )
## - authorization (role based authorization)
## - services (xml, csv, json, xmlrpc, jsonrpc, amf, rss)
## - crud actions
## (more options discussed in gluon/tools.py)
#########################################################################

from gluon.tools import *
from gluon.contrib import urlify
mail = Mail()                                  # mailer
auth = Auth(globals(),db)                      # authentication/authorization
crud = Crud(globals(),db)                      # for CRUD helpers using auth
service = Service(globals())                   # for json, xml, jsonrpc, xmlrpc, amfrpc
plugins = PluginManager()

mail.settings.server = 'logging' or 'smtp.gmail.com:587'  # your SMTP server
mail.settings.sender = 'you@gmail.com'         # your email
mail.settings.login = 'username:password'      # your credentials or None

# Janrain

# Get login URL for different dev environments
import os

base_url = 'http://localhost:8080'
env_name = 'SERVER_SOFTWARE'
if env_name in os.environ:
    server_software = os.environ[env_name]

    if server_software.startswith('Development'):
        base_url='http://localhost:8000'
    elif server_software.startswith('Google App Engine'):
        base_url='http://onthefattrack.appspot.com'


from gluon.contrib.login_methods.rpx_account import RPXAccount
auth.settings.actions_disabled=['register','change_password','request_reset_password']
auth.settings.login_form = RPXAccount(request,
    api_key='e9d4614579ac070748f11b635bc515157db893a3',
    domain='onthefattrack',
    url = "%s/%s/default/user/login" % (base_url, request.application))


# Custom Auth Table

def create_user_slug(row):
    first_name = row.first_name
    last_name = row.last_name

    slug = urlify.urlify(first_name + last_name, 512)
    original_slug = slug

    count = 2
    while len(db(db.auth_user.slug==slug).select()):
        slug = original_slug + str(count)
        count += 1

    return slug

# Define custom user table
db.define_table(
    auth.settings.table_user_name,

    # Required fields here 
    Field('first_name', length=128, default=''),
    Field('last_name', length=128, default=''),
    Field('email', length=128, default='', unique=True),
    Field('password', 'password', length=512,
          readable=False, label='Password'),
    Field('registration_key', length=512,
          writable=False, readable=False, default=''),
    Field('reset_password_key', length=512,
          writable=False, readable=False, default=''),
    Field('registration_id', length=512,
          writable=False, readable=False, default=''),

    # Custom fields here
    Field('slug', length=512, compute=create_user_slug,
        writable=False, readable=False, unique=True),
    )

# Required field requirements
custom_auth_table = db[auth.settings.table_user_name] # get the custom_auth_table
custom_auth_table.first_name.requires = \
        IS_NOT_EMPTY(error_message=auth.messages.is_empty)
custom_auth_table.last_name.requires = \
        IS_NOT_EMPTY(error_message=auth.messages.is_empty)
custom_auth_table.password.requires = [IS_STRONG(special=0), CRYPT()]
custom_auth_table.email.requires = [
        IS_EMAIL(error_message=auth.messages.invalid_email),
        IS_NOT_IN_DB(db, custom_auth_table.email)]

# Custom field requirements
custom_auth_table.slug.requires = [
        IS_SLUG(),
        IS_NOT_IN_DB(db, custom_auth_table.slug)]

# Virtual Fields
class AuthUserVirtualFields(object):
    def get_user_profile(self):
        rows = db(db.user_profile.user_id==self.auth_user.id).select()
        if (len(rows)):
            return rows.first()
        else:
            user_profile_id = db.user_profile.insert(user_id=self.auth_user.id)

            return db(db.user_profile.id==user_profile_id).select().first()

    def get_name(self):
        return self.auth_user.first_name + ' ' + self.auth_user.last_name


custom_auth_table.virtualfields.append(AuthUserVirtualFields())
        

auth.settings.table_user = custom_auth_table # tell auth to use custom_auth_table


auth.settings.hmac_key = 'sha512:59b7766e-e1a7-43c3-a867-c4acaaa483dd'   # before define_tables()
auth.define_tables()                           # creates all needed tables
auth.settings.mailer = mail                    # for user email verification
auth.settings.registration_requires_verification = False
auth.settings.registration_requires_approval = False
auth.messages.verify_email = 'Click on the link http://'+request.env.http_host+URL('default','user',args=['verify_email'])+'/%(key)s to verify your email'
auth.settings.reset_password_requires_verification = True
auth.messages.reset_password = 'Click on the link http://'+request.env.http_host+URL('default','user',args=['reset_password'])+'/%(key)s to reset your password'

#########################################################################
## If you need to use OpenID, Facebook, MySpace, Twitter, Linkedin, etc.
## register with janrain.com, uncomment and customize following
# from gluon.contrib.login_methods.rpx_account import RPXAccount
# auth.settings.actions_disabled=['register','change_password','request_reset_password']
# auth.settings.login_form = RPXAccount(request, api_key='...',domain='...',
#    url = "http://localhost:8000/%s/default/user/login" % request.application)
## other login methods are in gluon/contrib/login_methods
#########################################################################

crud.settings.auth = None                      # =auth to enforce authorization on crud

# Recaptcha
from gluon.tools import Recaptcha
auth.settings.captcha = Recaptcha(request,
    '6Lcy5MISAAAAAI_Ng_Hyv4K3xP42X1OOt1JdTfpa', '6Lcy5MISAAAAAAADqKsPgZT0lG2UDpcxLXyeBvYa')


#########################################################################
## Define your tables below (or better in another model file) for example
##
## >>> db.define_table('mytable',Field('myfield','string'))
##
## Fields can be 'string','text','password','integer','double','boolean'
##       'date','time','datetime','blob','upload', 'reference TABLENAME'
## There is an implicit 'id integer autoincrement' field
## Consult manual for more options, validators, etc.
##
## More API examples for controllers:
##
## >>> db.mytable.insert(myfield='value')
## >>> rows=db(db.mytable.myfield=='value').select(db.mytable.ALL)
## >>> for row in rows: print row.id, row.myfield
#########################################################################

