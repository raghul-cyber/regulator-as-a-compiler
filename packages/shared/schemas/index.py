# Shared Pydantic schemas

from pydantic import BaseModel

class RequirementBase(BaseModel):
    title: str
