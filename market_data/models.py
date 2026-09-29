from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

Symbol = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z][A-Z0-9.\-]{0,14}$"),
    BeforeValidator(lambda value: value.strip().upper() if isinstance(value, str) else value),
]


class Quote(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: Symbol
    price: Decimal = Field(gt=0, allow_inf_nan=False)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    as_of: AwareDatetime
    source: str
    is_sample: bool
