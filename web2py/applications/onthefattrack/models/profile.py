from datetime import date

# Profile Table


# Weight Table
db.define_table(
        'weight',
        Field('user_id', db.auth_user, default=auth.user.id if auth.user else None,
            writable=False, readable=False),
        Field('weight', 'double'),
        Field('date', 'date', default=date.today()),
        )

db['weight'].user_id.requires = IS_IN_DB(db, 'auth_user.id', '%(first_name)s %(last_name)s (%(id)d)')
db['weight'].weight.requires = [IS_FLOAT_IN_RANGE(0, 2000), IS_NOT_EMPTY()]
db['weight'].date.requires = IS_DATE(format=T('%d %b %Y'), error_message=T('must be MM/DD/YYY'))
