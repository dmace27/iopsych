"""Standard API problem-detail response contracts."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ProblemCode = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]


class ApiFieldError(BaseModel):
    """A request validation issue located with a JSON Pointer."""

    model_config = ConfigDict(extra="forbid")

    pointer: Annotated[str, StringConstraints(pattern=r"^(?:$|/)")]
    code: ProblemCode
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ApiProblem(BaseModel):
    """RFC 9457 problem details plus stable machine-readable extensions."""

    model_config = ConfigDict(extra="forbid")

    type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = "about:blank"
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    status: Annotated[int, Field(strict=True, ge=400, le=599)]
    detail: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None
    instance: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None
    code: ProblemCode
    errors: list[ApiFieldError] | None = None
