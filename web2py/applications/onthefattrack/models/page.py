from datetime import date, datetime

# Profile Table
db.define_table(
        'user_profile',
        Field('user_id', db.auth_user, default=auth.user_id if auth.user else None,
            writable=False, readable=False),
        Field('weight_unit', length=10, default='lbs'),
        )

db.user_profile.user_id.requires = IS_IN_DB(db, db.auth_user.id)
db.user_profile.weight_unit.requires = IS_IN_SET(['lbs', 'kgs', 'stone'])

# Weight Table
db.define_table(
        'weight',
        Field('user_id', db.auth_user, default=auth.user_id if auth.user else None,
            writable=False, readable=False, unique=True),
        Field('weight', 'double'),
        Field('timestamp', 'datetime', default=datetime.now(),
            writable=False, readable=False),
        Field('date', 'date', default=date.today()),
        )

db.weight.user_id.requires = IS_IN_DB(db, db.auth_user.id)
db.weight.weight.requires = [IS_FLOAT_IN_RANGE(0, 2000), IS_NOT_EMPTY()]
db.weight.date.requires = IS_DATE(format=T('%Y-%m-%d'), error_message=T('must be YYYY-MM-DD'))

def get_page_id():
    ret_val = None

    if 'page_id' in request.post_vars:
        ret_val = int(request.post_vars.page_id)

    return ret_val

# Post Table
db.define_table(
        'post',
        Field('author_id', db.auth_user, default=auth.user_id if auth.user else None,
            writable=False, readable=False),
        Field('page_id', db.auth_user, default=get_page_id,
            writable=False, readable=False),
        Field('date', 'datetime', default=datetime.now(),
            writable=False, readable=False),
        Field('edit_date', 'datetime', default=datetime.now(), update=datetime.now(),
            writable=False, readable=False),
        Field('text', 'text'),
        )

# Virtual Fields
class PostVirtualFields(object):
    def get_author(self):
        def lazy(self=self):
            ret_val = None

            rows = db(db.auth_user.id==self.post.author_id).select()
            if (len(rows)):
                ret_val = rows.first()

            return ret_val
        return lazy

    def get_page_user(self):
        def lazy(self=self):
            ret_val = None

            rows = db(db.auth_user.id==self.post.page_id).select()
            if (len(rows)):
                ret_val = rows.first()

            return ret_val
        return lazy

db.post.virtualfields.append(PostVirtualFields())


db.post.author_id.requires = IS_IN_DB(db, db.auth_user.id)
db.post.page_id.requires = IS_IN_DB(db, db.auth_user.id)
db.post.text.requires = IS_NOT_EMPTY()

# Comment Table
db.define_table(
        'comment',
        Field('author_id', db.auth_user, default=auth.user_id if auth.user else None,
            writable=False, readable=False),
        Field('post_id', db.post,
            writable=False, readable=False),
        Field('date', 'datetime', default=datetime.now(),
            writable=False, readable=False),
        Field('text', 'text'),
        )

db.comment.author_id.requires = IS_IN_DB(db, db.auth_user.id)
