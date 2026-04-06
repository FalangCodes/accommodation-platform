import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config # type: ignore 
from sqlalchemy import pool

from alembic import context # type: ignore

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "app"))

# Import your Base and ALL models here
from app.db.base import Base
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.university import University
from app.models.accommodation import Accommodation, AccommodationView, AccommodationImage
from app.models.review import Review, ReviewNLPResult, ReviewReply
from app.models.moderation import ModerationLog, ModerationQueue, Appeal
# ... import any other models you created ...

# This is the MetaData object that contains the table definitions
target_metadata = Base.metadata

# ... rest of your env.py file ...