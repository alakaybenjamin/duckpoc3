from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    search_history = relationship("SearchHistory", back_populates="user")
    collections = relationship("Collection", back_populates="user")

class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    query = Column(String)
    category = Column(String)
    filters = Column(JSON)
    results_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_saved = Column(Boolean, default=False)
    last_used = Column(DateTime, default=datetime.utcnow)
    use_count = Column(Integer, default=0)
    name = Column(String(1000), nullable=True)  # Name for saved searches, nullable
    user = relationship("User", back_populates="search_history")

class ClinicalStudy(Base):
    __tablename__ = "clinical_study"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    status = Column(String)
    phase = Column(String)
    drug = Column(String)  # Added field for drug name
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    relevance_score = Column(Float, default=1.0)
    indication_category = Column(String)  # Added field
    procedure_category = Column(String)   # Added field
    severity = Column(String)            # Added field
    risk_level = Column(String)          # Added field
    duration = Column(Integer)           # Added field
    institution = Column(String)         # Added field for institution name
    participant_count = Column(Integer)  # Added field for number of participants
    
    # Changed from one-to-one to one-to-many (up to 2 data products)
    data_products = relationship("DataProduct", back_populates="study")

class Indication(Base):
    __tablename__ = "indication"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    category = Column(String)
    severity = Column(String)
    relevance_score = Column(Float, default=1.0)

class Procedure(Base):
    __tablename__ = "procedure"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    category = Column(String)
    risk_level = Column(String)
    duration = Column(Integer)  # in minutes
    relevance_score = Column(Float, default=1.0)

class DataProduct(Base):
    __tablename__ = "data_products"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    study_id = Column(Integer, ForeignKey("clinical_study.id"))
    type = Column(String)  # e.g., Dataset, Algorithm, Image Collection
    format = Column(String)  # e.g., CSV, JSON, DICOM
    size = Column(String)  # e.g., 2.5 GB
    access_level = Column(String, default="Public")  # Public, Restricted, Private
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship with study (many-to-one)
    study = relationship("ClinicalStudy", back_populates="data_products")
    # Relationship with collections through collection_items
    collections = relationship("CollectionItem", back_populates="data_product")

class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="collections")
    items = relationship("CollectionItem", back_populates="collection")

class CollectionItem(Base):
    __tablename__ = "collection_items"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"))
    data_product_id = Column(Integer, ForeignKey("data_products.id"))
    added_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    collection = relationship("Collection", back_populates="items")
    data_product = relationship("DataProduct", back_populates="collections")

class ScientificPaper(Base):
    __tablename__ = "scientific_papers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    abstract = Column(String)
    authors = Column(JSON)  # List of authors
    publication_date = Column(DateTime)
    journal = Column(String)
    doi = Column(String, unique=True)
    keywords = Column(JSON)  # List of keywords
    citations_count = Column(Integer, default=0)
    reference_list = Column(JSON)  # List of referenced papers (renamed from 'references')
    created_at = Column(DateTime, default=datetime.utcnow)

class DataDomainMetadata(Base):
    __tablename__ = "data_domain_metadata"

    id = Column(Integer, primary_key=True, index=True)
    domain_name = Column(String)
    description = Column(String)
    schema_definition = Column(JSON)  # JSON Schema for the domain
    validation_rules = Column(JSON)  # Domain-specific validation rules
    data_format = Column(String)  # e.g., CSV, JSON, XML
    sample_data = Column(JSON)  # Sample data structure
    owner = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)