from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql.functions import now
from base import Base

class Review(Base):
    __tablename__ = 'reviews'
    
    id = Column(Integer, primary_key=True)
    steam_id = Column(String(100), nullable=False)
    username = Column(String(250), nullable=False)
    review = Column(String(500), nullable=False)
    rating = Column(String(20), nullable=False)
    game_id = Column(Integer, nullable=False)
    date_created = Column(DateTime, nullable=False)
    trace_id = Column(String(100), nullable=False)

    def __init__ (self, steam_id, username, review, rating, game_id, trace_id):
        self.steam_id = steam_id
        self.username = username
        self.review = review
        self.rating = rating
        self.game_id = game_id
        self.date_created = now()
        self.trace_id = trace_id

    def to_dict(self):
        dict = {}
        dict['id'] = self.id
        dict['steam_id'] = self.steam_id
        dict['username'] = self.username
        dict['review'] = self.review
        dict['rating'] = self.rating
        dict['game_id'] = self.game_id
        dict['date_created'] = self.date_created
        dict['trace_id'] = self.trace_id    

        return dict