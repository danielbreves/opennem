import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from opennem.api.exceptions import OpennemBaseHttpException
from opennem.db import get_database_session
from opennem.db.models.opennem import Feedback
from opennem.notifications.trello import post_trello_card
from opennem.schema.types import TwitterHandle

logger = logging.getLogger(__name__)

router = APIRouter()


class NetworkNotFound(OpennemBaseHttpException):
    detail = "Network not found"


class UserFeedbackSubmission(BaseModel):
    subject: str
    description: Optional[str]
    email: Optional[EmailStr]
    twitter: Optional[TwitterHandle]


@router.post("/")
def feedback_submissions(
    user_feedback: UserFeedbackSubmission, session: Session = Depends(get_database_session)
) -> Any:
    """User feedback submission"""
    feedback = Feedback(
        subject=user_feedback.subject,
        description=user_feedback.description,
        email=user_feedback.email,
        twitter=user_feedback.twitter,
    )

    session.add(feedback)

    post_trello_card(subject=user_feedback.subject, description=user_feedback.description)

    return {"status": "OK"}
