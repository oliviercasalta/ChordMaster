import sqlalchemy

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime

# Create an SQLalchemy engine from URL TCP
engine = create_engine('mysql+pymysql://root:root@127.0.0.1/tab')

# Defining Metadata
metadata = MetaData()

# Create a new tables
""" users """
users = Table('users', metadata,
Column('id', Integer, primary_key=True),
Column('username', String(50)),
Column('hash', String(255)))

""" song_list """
song_list = Table('song_list', metadata,
Column('song_id', Integer, primary_key=True),
Column('user_id', String(50)),
Column('song_name', String(50)),
Column('time', DateTime))

""" song_modif """
song_modif = Table('song_modif', metadata,
Column('song_modif_id', Integer, primary_key=True),
Column('user_id', String(50)),
Column('song_name', String(50)),
Column('time', DateTime))

metadata.create_all(engine)
print('table created : {}, {}, {} '.format(users, song_list, song_modif)) 