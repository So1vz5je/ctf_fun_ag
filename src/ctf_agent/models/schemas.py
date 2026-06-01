"""Pydantic models for GZCTF API responses."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import AliasChoices, BaseModel, Field


class ChallengeType(StrEnum):
    STATIC_ATTACHMENT = "StaticAttachment"
    STATIC_CONTAINER = "StaticContainer"
    DYNAMIC_ATTACHMENT = "DynamicAttachment"
    DYNAMIC_CONTAINER = "DynamicContainer"


class ChallengeTag(StrEnum):
    MISC = "Misc"
    CRYPTO = "Crypto"
    PWN = "Pwn"
    WEB = "Web"
    REVERSE = "Reverse"
    BLOCKCHAIN = "Blockchain"
    FORENSICS = "Forensics"
    HARDWARE = "Hardware"
    MOBILE = "Mobile"
    PPC = "PPC"
    AI = "AI"
    OSINT = "OSINT"
    PENTEST = "PenTest"


class UserProfile(BaseModel):
    user_id: str = Field(alias="userId", default="")
    user_name: str = Field(alias="userName", default="")
    email: str = ""
    role: str = ""
    avatar: str | None = None

    model_config = {"populate_by_name": True}


class GameInfo(BaseModel):
    id: int
    title: str = ""
    summary: str = ""
    poster: str | None = None
    team_count: int = Field(
        validation_alias=AliasChoices("teamCount", "team_count"),
        default=0,
    )
    start_time: datetime | None = Field(
        validation_alias=AliasChoices("start", "startTimeUtc", "start_time"),
        default=None,
    )
    end_time: datetime | None = Field(
        validation_alias=AliasChoices("end", "endTimeUtc", "end_time"),
        default=None,
    )
    status: str = ""

    model_config = {"populate_by_name": True, "extra": "allow"}


class GameDetail(BaseModel):
    id: int
    title: str = ""
    content: str = ""
    accept_without_review: bool = Field(alias="acceptWithoutReview", default=False)
    team_member_count_limit: int = Field(alias="teamMemberCountLimit", default=0)
    container_count_limit: int = Field(alias="containerCountLimit", default=3)
    start_time: datetime | None = Field(
        validation_alias=AliasChoices("start", "startTimeUtc", "start_time"),
        default=None,
    )
    end_time: datetime | None = Field(
        validation_alias=AliasChoices("end", "endTimeUtc", "end_time"),
        default=None,
    )
    participated: bool = False
    status: str = ""

    model_config = {"populate_by_name": True, "extra": "allow"}


class Attachment(BaseModel):
    type: str = ""
    url: str | None = None
    file_name: str | None = Field(alias="fileName", default=None)

    model_config = {"populate_by_name": True, "extra": "allow"}


class ChallengeInfo(BaseModel):
    """Challenge summary in game details listing."""

    id: int
    title: str = ""
    tag: str = ""
    score: int = 0
    is_solved: bool = Field(alias="isSolved", default=False)
    type: str = ""

    model_config = {"populate_by_name": True, "extra": "allow"}


class ContainerInfo(BaseModel):
    status: str = ""
    entry: str = ""
    start_time: datetime | None = Field(alias="startTime", default=None)
    expect_stop_at: datetime | None = Field(alias="expectStopAt", default=None)

    model_config = {"populate_by_name": True, "extra": "allow"}


class ChallengeDetail(BaseModel):
    """Full challenge details."""

    id: int
    title: str = ""
    content: str = ""
    tag: str = ""
    score: int = 0
    type: str = ""
    hints: list[str] = Field(default_factory=list)
    attachment: Attachment | None = None
    container: ContainerInfo | None = None
    is_solved: bool = Field(alias="isSolved", default=False)
    submission_count: int = Field(alias="submissionCount", default=0)

    model_config = {"populate_by_name": True, "extra": "allow"}

    @property
    def is_container_based(self) -> bool:
        return self.type in (
            ChallengeType.STATIC_CONTAINER,
            ChallengeType.DYNAMIC_CONTAINER,
        )

    @property
    def has_attachment(self) -> bool:
        return self.attachment is not None and self.attachment.url is not None


class SubmissionResult(BaseModel):
    status: str = ""
    answer: str = ""

    model_config = {"populate_by_name": True}
