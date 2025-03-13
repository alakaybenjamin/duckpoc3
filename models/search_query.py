from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class SearchQuery(BaseModel):
    """Model for search queries"""
    terms: List[str]
    collection_type: str = "clinical_study"
    page: int = 1
    per_page: int = 10
    filters: Dict = {}
    schema_type: str = "default"
    user_context: Optional[Dict[str, Any]] = None 