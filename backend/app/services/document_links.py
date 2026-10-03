def landlord_document_link(landlord_id, kind, reference):
    return f"/api/v1/landlords/{landlord_id}/documents/{kind}" if reference else None


def ownership_document_link(accommodation_id, reference):
    return f"/api/v1/accommodations/{accommodation_id}/documents/ownership" if reference else None


async def listing_document_response(db, data, accommodation, user):
    """Strip legacy cached blob URLs, then add an authorized endpoint path."""
    from sqlalchemy import select
    from app.models.landlord import Landlord
    output = {key: value for key, value in data.items() if key != "ownership_doc_url"}
    allowed = user and user.role in ("admin", "moderator")
    if user and user.role == "landlord":
        result = await db.execute(select(Landlord).where(
            Landlord.user_id == user.id, Landlord.id == accommodation.landlord_id,
        ))
        allowed = result.scalar_one_or_none() is not None
    if allowed:
        output["ownership_doc_url"] = ownership_document_link(accommodation.id, accommodation.ownership_doc_url)
    return output
