# import sqlite3
import mysql.connector

# conn = sqlite3.connect('reviews.db')
# c = conn.cursor()

db_conn = mysql.connector.connect(host="localhost", user="Kris", password="Kiwi!0313", database="reviews_db")
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