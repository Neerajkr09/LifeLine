from pydantic import BaseModel


class RecipientDashboardStats(BaseModel):
    requests_raised: int = 0
    successful_requests: int = 0
    active_requests: int = 0
    willing_donor_count: int = 0


class DonorDashboardStats(BaseModel):
    matching_requests_nearby: int = 0
    times_volunteered: int = 0
    confirmed_donations: int = 0
