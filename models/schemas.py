import logging
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Dict, Any, Sequence, List
from datetime import datetime

logger = logging.getLogger(__name__)

class UserBase(BaseModel):
    email: EmailStr
    username: str

class User(UserBase):
    id: int
    is_active: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class SearchQuery(BaseModel):
    q: str
    category: Optional[str] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = None

class SearchResult(BaseModel):
    id: int
    title: str
    type: str
    description: Optional[str] = None
    relevance_score: float = 1.0
    data: Optional[Dict[str, Any]] = None
    data_products: Optional[Sequence[Dict[str, Any]]] = None

    model_config = ConfigDict(from_attributes=True)

class SearchResponse(BaseModel):
    results: Sequence[SearchResult]
    total: int
    page: int
    per_page: int

    model_config = ConfigDict(from_attributes=True)

class SearchHistoryEntry(BaseModel):
    id: int
    user_id: int
    query: str
    category: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    results_count: int
    created_at: datetime
    is_saved: bool = False
    last_used: datetime
    use_count: int = 0

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        populate_by_name=True
    )

class DataProductBase(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    type: str
    format: str
    study_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CollectionItemBase(BaseModel):
    id: int
    data_product: DataProductBase
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CollectionCreate(BaseModel):
    title: str
    description: Optional[str] = None

class CollectionSchema(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: Sequence[CollectionItemBase] = []

    model_config = ConfigDict(from_attributes=True)

class CollectionItemCreate(BaseModel):
    data_product_ids: Sequence[int]

    model_config = ConfigDict(from_attributes=True)

class ClinicalStudyDetail(BaseModel):
    status: Optional[str] = None
    phase: Optional[str] = None
    drug: Optional[str] = None
    institution: Optional[str] = None
    participant_count: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    indication_category: Optional[str] = None
    procedure_category: Optional[str] = None
    severity: Optional[str] = None
    risk_level: Optional[str] = None
    duration: Optional[int] = None

class DataProductDetail(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    type: str
    format: Optional[str] = None
    size: Optional[str] = None
    access_level: Optional[str] = None

class ClinicalStudyResult(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    relevance_score: float = 1.0
    study_details: ClinicalStudyDetail
    data_products: List[DataProductDetail]

class ClinicalStudyCustomResponse(BaseModel):
    pagination: Dict[str, Any]
    results: List[ClinicalStudyResult]

    model_config = ConfigDict(from_attributes=True)