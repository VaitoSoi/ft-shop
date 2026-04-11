from datetime import datetime, timedelta
from enum import Enum as PyEnum
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel as PyBaseModel, ConfigDict
from sqlalchemy import JSON, Column, Enum as SQLEnum, TypeDecorator
from sqlmodel import Field, Relationship, SQLModel

from app.lib.env import EXPIRE_TIME


class PydanticJSON(TypeDecorator):
    impl = JSON

    def __init__(self, pydantic_model: type[Any]):
        super().__init__()
        if not issubclass(pydantic_model, PyBaseModel):
            raise ValueError("pydantic_model must be a subclass of pydantic BaseModel")
        self.pydantic_model = pydantic_model

    def process_bind_param(self, value: PyBaseModel | None, dialect) -> dict | None:
        # Python -> Database (Saving)
        if value is None:
            return None
        if isinstance(value, SQLModel):
            return value.model_dump(mode="json")
        return cast(Any, value)

    def process_result_value(self, value: dict | None, dialect) -> PyBaseModel | None:
        # Database -> Python (Loading)
        if value is None:
            return None
        return self.pydantic_model.model_validate(value)


class ShopItem(PyBaseModel):
    id: int
    name: str
    description: str
    old_prices: list
    limited: bool
    stock: int  | None
    type: str
    show_in_carousel: bool
    accessory_tag: str
    agh_contents: str
    attached_shop_item_ids: list
    buyable_by_self: bool
    long_description: str
    max_qty: int  | None
    one_per_person_ever: bool
    sale_percentage: int | None
    requires_achievement: list
    image_url: str
    enabled: "ShopItemEnable"
    ticket_cost: ShopItemCost


class ShopItemEnable(PyBaseModel):
    enabled_au: bool
    enabled_ca: bool
    enabled_eu: bool
    enabled_in: bool
    enabled_uk: bool
    enabled_us: bool
    enabled_xx: bool


class ShopItemCost(PyBaseModel):
    model_config = ConfigDict(populate_by_name=True)

    base_cost: int
    au: int
    ca: int
    eu: int
    in_: int = Field(alias="in")
    uk: int
    us: int
    xx: int


class SubscriptionType(PyEnum):
    compact = "compact"
    full = "full"


class BaseModel(SQLModel):
    __abstract__ = True

    id: str = Field(primary_key=True, default_factory=lambda: str(uuid4()))

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(
        default_factory=datetime.now, sa_column_kwargs={"onupdate": datetime.now}
    )


class User(BaseModel, table=True):
    __tablename__ = "user"  # type: ignore

    username: str
    password: str


class Subscription(BaseModel, table=True):
    __tablename__ = "subscription"  # type: ignore

    user_id: str = Field(foreign_key="user.id")
    user: User = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    events: Literal["all"] | list[str] = Field(sa_column=Column(JSON))

    headers: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    endpoint: str
    type: SubscriptionType = Field(
        sa_column=Column(SQLEnum(SubscriptionType))
    )


class SlicedSubscription(PyBaseModel):
    id: str

    events: Literal["all"] | list[str]
    headers: dict[str, Any] | None
    endpoint: str
    type: SubscriptionType


class Token(BaseModel, table=True):
    __tablename__ = "token"  # type: ignore

    user_id: str = Field(foreign_key="user.id")
    user: User = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    token: str
    revoked: bool = Field(default=False)
    expired_at: datetime = Field(
        default_factory=lambda: datetime.now() + timedelta(milliseconds=EXPIRE_TIME)
    )

class SubscriptionResponse(BaseModel, table=True):
    __tablename__ = "responses" # type: ignore

    subscription_id: str = Field(foreign_key="subscription.id")
    subscription: Subscription = Relationship()

    status_code: int
    header: dict = Field(sa_column=Column(JSON))
    data: str | dict = Field(sa_column=Column(JSON))


class Changes(BaseModel, table=True):
    __tablename__ = "changes"  # type: ignore

    old: ShopItem = Field(sa_column=Column(PydanticJSON(ShopItem)))
    new: ShopItem = Field(sa_column=Column(PydanticJSON(ShopItem)))
    changes: list[str] = Field(sa_column=Column(JSON))
