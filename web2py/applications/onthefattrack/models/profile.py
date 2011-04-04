from datetime import date, datetime

# Profile Table
db.define_table(
        'user_profile',
        Field('user_id', db.auth_user, default=auth.user_id if auth.user else None,
            writable=False, readable=False),
        Field('weight_unit', length=10, default='lbs'),
        )

db['user_profile'].weight_unit.requires = IS_IN_SET(['lbs', 'kgs', 'stone'])

# Weight Table
db.define_table(
        'weight',
        Field('user_id', db.auth_user, default=auth.user_id if auth.user else None,
            writable=False, readable=False, unique=True),
        Field('weight', 'double'),
        Field('date', 'date', default=date.today()),
        )

db['weight'].weight.requires = [IS_FLOAT_IN_RANGE(0, 2000), IS_NOT_EMPTY()]
db['weight'].date.requires = IS_DATE(format=T('%d %b %Y'), error_message=T('must be MM/DD/YYY'))

# Post Table
db.define_table(
        'post',
        Field('user_id', db.auth_user, default=auth.user_id if auth.user else None,
            writable=False, readable=False),
        Field('date', 'datetime', default=datetime.now(),
            writable=False, readable=False),
        Field('edit_date', 'datetime', default=datetime.now(), update=datetime.now(),
            writable=False, readable=False),
        Field('text', 'text'),
        )

# Comment Table
db.define_table(
        'comment',
        Field('user_id', db.auth_user, default=auth.user_id if auth.user else None,
            writable=False, readable=False),
        Field('post_id', db.post,
            writable=False, readable=False),
        Field('date', 'datetime', default=datetime.now(),
            writable=False, readable=False),
        Field('text', 'text'),
        )

