from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_city_or_404
from app.db.session import get_db
from app.models.city import City
from app.schemas.recommendation import OrganizationOut, RecommendationsOut
from app.services.recommendation_service import get_all_organizations, get_all_tips, get_city_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationsOut)
def get_recommendations(city: City = Depends(get_city_or_404), db: Session = Depends(get_db)):
    city_data = get_city_recommendations(db, city)
    all_orgs = get_all_organizations()

    org_by_name = {o.name: o for o in all_orgs}
    recommended = [org_by_name[name] for name in city_data["relevant_organization_names"] if name in org_by_name]

    return RecommendationsOut(
        city_insights=city_data["city_insights"],
        tips=get_all_tips(),
        recommended_organizations=[
            OrganizationOut(name=o.name, category=o.category, description=o.description, website=o.website)
            for o in recommended
        ],
        all_organizations=[
            OrganizationOut(name=o.name, category=o.category, description=o.description, website=o.website)
            for o in all_orgs
        ],
    )
