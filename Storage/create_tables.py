# import sqlite3
import mysql.connector
import yaml
<<<<<<< HEAD
=======

with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())
>>>>>>> f970313b061d5ee186037d8117883270e7188cd8

with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())
# conn = sqlite3.connect('reviews.db')
# c = conn.cursor()

db_conn = mysql.connector.connect(
    host=app_config['datastore']['hostname'],
    user=app_config['datastore']['user'],
    password=app_config['datastore']['password'],
    database=app_config['datastore']['db'],
    port=app_config['datastore']['port']
)
db_cursor = db_conn.cursor()

db_cursor.execute('''
        CREATE TABLE reviews
        (id INT NOT NULL AUTO_INCREMENT,
        steam_id TEXT NOT NULL,
        username TEXT NOT NULL,
        review TEXT NOT NULL,
        rating TEXT NOT NULL,
        game_id INTEGER NOT NULL,
        date_created TEXT NOT NULL,
        trace_id VARCHAR(100) NOT NULL,
        CONSTRAINT get_all_reviews_pk PRIMARY KEY (id))
          ''')

db_cursor.execute('''
        CREATE TABLE ratings
        (id INT NOT NULL AUTO_INCREMENT,
        game_id INTEGER NOT NULL,
        game_name TEXT NOT NULL,
        rating TEXT NOT NULL,
        num_reviews INTEGER NOT NULL,
        date_created TEXT NOT NULL,
        trace_id VARCHAR(100) NOT NULL,
        CONSTRAINT rating_game_pk PRIMARY KEY (id))
          ''')

db_conn.commit()
db_conn.close()
