from pydantic import BaseModel


class ReportRequest(BaseModel):
    city_id: int
    format: str = "pdf"  # "pdf" | "csv"
    days: int = 30
