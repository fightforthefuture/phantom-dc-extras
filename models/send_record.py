from datetime import datetime
from sqlalchemy import func, Column, BigInteger, SmallInteger, Integer, \
    String, DateTime, ForeignKey, Text, Float
from sqlalchemy.exc import SQLAlchemyError
from models import db

class SendRecord(db.Model):
    __tablename__ = 'send_record'

    id              = Column(BigInteger, primary_key=True)
    source_uid      = Column(String(255),nullable=True)
    campaign        = Column(String(255),nullable=True,unique=False,index=True)
    bioguide_id     = Column(String(255))
    chamber         = Column(String(16), nullable=True)
    recipient_name  = Column(String(255), nullable=True)
    create_date     = Column(DateTime)
    mod_date        = Column(DateTime)

    def __init__(self,source_uid,campaign,bioguide_id,chamber,recipient_name):

        self.create_date    = datetime.now()
        self.source_uid     = source_uid
        self.campaign       = campaign
        self.bioguide_id    = bioguide_id
        self.chamber        = chamber
        self.recipient_name = recipient_name

    def __repr__(self):
        return "<SendRecord(id='%s', uid='%s')>" % (self.id, self.source_uid)