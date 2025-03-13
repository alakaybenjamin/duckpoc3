"""
Initialize the search registries at application startup.
"""
import logging
from services.search.base import SchemaRegistry
from services.search.transformers import (
    DefaultSchemaTransformer,
    CompactSchemaTransformer,
    DetailedSchemaTransformer,
    ScientificPaperSchemaTransformer,
    DataDomainSchemaTransformer,
    ClinicalStudyCustomTransformer
)

logger = logging.getLogger(__name__)

def init_registries():
    """Initialize the search registries"""
    # Register transformers
    SchemaRegistry._transformers = {
        'default': DefaultSchemaTransformer,
        'compact': CompactSchemaTransformer,
        'detailed': DetailedSchemaTransformer,
        'scientific_paper': ScientificPaperSchemaTransformer,
        'data_domain': DataDomainSchemaTransformer,
        'clinical_study_custom': ClinicalStudyCustomTransformer
    }
    
    logger.debug(f"Registered transformers: {list(SchemaRegistry._transformers.keys())}")

# Run the initialization on import
init_registries() 