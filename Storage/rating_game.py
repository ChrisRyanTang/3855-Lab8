from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql.functions import now
from base import Base



class Rating(Base):
    __tablename__ = 'ratings'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, nullable=False)
    game_name = Column(String(250), nullable=False)
    rating = Column(String(20), nullable=False)
    num_reviews = Column(Integer, nullable=False)
    date_created = Column(DateTime, nullable=False)
    trace_id = Column(String(100), nullable=False)

    def __init__ (self, game_id, game_name, rating, num_reviews, trace_id):
        self.game_id = game_id
        self.game_name = game_name
        self.rating = rating
        self.num_reviews = num_reviews
        self.date_created = now()
        self.trace_id = trace_id

    def to_dict(self):
        dict = {}
        dict['id'] = self.id
        dict['game_id'] = self.game_id
        dict['game_name'] = self.game_name
        dict['rating'] = self.rating
        dict['num_reviews'] = self.num_reviews
        dict['date_created'] = self.date_created
        dict['trace_id'] = self.trace_id

        return dict