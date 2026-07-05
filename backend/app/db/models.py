# This file exists solely to import all models in one place
# so SQLAlchemy can resolve all relationships.
# Import this file anywhere you need all models loaded.
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.university import University
from app.models.accommodation import Accommodation, AccommodationView, AccommodationImage
from app.models.review import Review, ReviewNLPResult, ReviewReply
from app.models.moderation import ModerationLog, ModerationQueue, Appeal
from app.models.report import MonthlyReport, ReportMetric
from app.models.insight import AccommodationInsight