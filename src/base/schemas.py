from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, TypeAdapter
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.sql.type_api import TypeEngine
from sqlalchemy.types import TypeDecorator

T = TypeVar("T")


class PydanticJSONB(TypeDecorator, Generic[T]):
    """
    SQLAlchemy type that stores Pydantic v2-validated data in JSON/JSONB.

    - Uses JSONB on PostgreSQL, JSON elsewhere.
    - `T` can be:
        * A BaseModel subclass
        * A typing construct, e.g.:
            Annotated[Union[EmailJob, SmsJob], Field(discriminator="kind")]
    """

    impl = sa.JSON
    cache_ok: bool = True

    pydantic_type: Any
    _adapter: TypeAdapter[T]

    def __init__(self, pydantic_type: Any) -> None:
        super().__init__()
        self.pydantic_type = pydantic_type
        self._adapter = TypeAdapter(pydantic_type)

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(sa.JSON())

    def process_bind_param(
        self,
        value: T | BaseModel | dict[str, Any] | None,
        dialect: Dialect,
    ) -> Any | None:
        if value is None:
            return None
        model_value: T = self._adapter.validate_python(value)
        return self._adapter.dump_python(model_value, mode="json")

    def process_result_value(
        self,
        value: Any,
        dialect: Dialect,
    ) -> T | None:
        if value is None:
            return None
        return self._adapter.validate_python(value)


class BaseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime | None
