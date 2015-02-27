from datetime import datetime
from sqlalchemy import func, Column, BigInteger, SmallInteger, Integer, \
    String, DateTime, ForeignKey, Text, Float
from sqlalchemy.exc import SQLAlchemyError
from models import db

class Log(db.Model):
    __tablename__ = 'log'

    id              = Column(BigInteger, primary_key=True)
    log_type        = Column(String(255),nullable=False,unique=False,index=True)
    log             = Column(Text)
    input_data      = Column(Text)
    bioguide_id     = Column(String(16), nullable=True)
    chamber         = Column(String(16), nullable=True)
    recipient_name  = Column(String(255), nullable=True)
    create_date     = Column(DateTime)
    mod_date        = Column(DateTime)
    uid             = Column(String(255), unique=False, index=True)

    def __init__(self, log_type, log, input_data, uid=None, bioguide_id=None, \
            chamber=None, recipient_name=None):

        self.create_date    = datetime.now()
        self.log_type       = log_type
        self.log            = log
        self.input_data     = input_data
        self.uid            = uid
        self.bioguide_id    = bioguide_id
        self.chamber        = chamber
        self.recipient_name = recipient_name

    def __repr__(self):
        return "<Log(id='%s', type='%s')>" % (self.id, self.log_type)