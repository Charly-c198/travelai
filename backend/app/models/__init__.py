"""数据模型包：导入所有模型，使 Base.metadata 能收集全部表"""
from app.models.user import User
from app.models.trip import Trip, ItineraryDay, ItinerarySpot
from app.models.spot import Spot
from app.models.booking import Booking
from app.models.conversation_message import ConversationMessage
from app.models.plan_cache import PlanCache
from app.models.shared_trip import SharedTrip
from app.models.user_profile import UserProfile
from app.models.tracking_event import TrackingEvent
from app.models.quota_usage import QuotaUsage
from app.models.generation_metric import GenerationMetric
from app.models.planning_session import PlanningSession

__all__ = ["User", "Trip", "ItineraryDay", "ItinerarySpot", "Spot", "Booking", "ConversationMessage", "PlanCache", "SharedTrip", "UserProfile", "TrackingEvent", "QuotaUsage", "GenerationMetric", "PlanningSession"]