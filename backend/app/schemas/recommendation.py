from pydantic import BaseModel


class CivicTipOut(BaseModel):
    title: str
    body: str
    category: str


class OrganizationOut(BaseModel):
    name: str
    category: str
    description: str
    website: str


class RecommendationsOut(BaseModel):
    city_insights: list[str]
    tips: list[CivicTipOut]
    recommended_organizations: list[OrganizationOut]
    all_organizations: list[OrganizationOut]
