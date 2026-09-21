"""
Importing every model module here ensures they all register on
`Base.metadata` before Alembic autogenerate or `Base.metadata.create_all`
run - a common gotcha in SQLAlchemy projects.
"""
from app.models.city import City
from app.models.ward import Ward
from app.models.location import Location
from app.models.image import Image
from app.models.detection import Detection
from app.models.problem import Problem
from app.models.risk_score import RiskScore
from app.models.resolution import Resolution

__all__ = [
    "City",
    "Ward",
    "Location",
    "Image",
    "Detection",
    "Problem",
    "RiskScore",
    "Resolution",
]
