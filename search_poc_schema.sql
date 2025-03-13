-- Search POC Schema DDL
-- This file contains all DDL statements for tables and indexes in the search_poc schema
-- Including grant statements for select, insert, and update permissions

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS search_poc;

-- Set search path
SET search_path TO search_poc;

-- Users table
CREATE TABLE search_poc.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256),
    api_token VARCHAR(100) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clinical Studies table
CREATE TABLE search_poc.clinical_study (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Active',
    phase VARCHAR(50),
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    institution VARCHAR(255),
    participant_count INTEGER,
    relevance_score FLOAT DEFAULT 1.0,
    indication_category VARCHAR(100),
    procedure_category VARCHAR(100),
    severity VARCHAR(50),
    risk_level VARCHAR(50),
    duration INTEGER
);

-- Data Products table
CREATE TABLE search_poc.data_products (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    study_id INTEGER REFERENCES search_poc.clinical_study(id),
    type VARCHAR(100),
    format VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Collections table
CREATE TABLE search_poc.collections (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    user_id INTEGER REFERENCES search_poc.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Collection Items table
CREATE TABLE search_poc.collection_items (
    id SERIAL PRIMARY KEY,
    collection_id INTEGER REFERENCES search_poc.collections(id),
    data_product_id INTEGER REFERENCES search_poc.data_products(id),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Search History table
CREATE TABLE search_poc.search_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES search_poc.users(id),
    query VARCHAR(255) NOT NULL,
    category VARCHAR(50),
    filters JSONB,
    results_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_saved BOOLEAN DEFAULT FALSE,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    use_count INTEGER DEFAULT 0
);

-- Scientific Papers table
CREATE TABLE search_poc.scientific_papers (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    abstract TEXT,
    authors JSONB,
    publication_date TIMESTAMP,
    journal VARCHAR(100),
    doi VARCHAR(100) UNIQUE,
    keywords JSONB,
    citations_count INTEGER DEFAULT 0,
    reference_list JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data Domain Metadata table
CREATE TABLE search_poc.data_domain_metadata (
    id SERIAL PRIMARY KEY,
    domain_name VARCHAR(100) NOT NULL,
    description TEXT,
    schema_definition JSONB,
    validation_rules JSONB,
    data_format VARCHAR(50),
    sample_data JSONB,
    owner VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===========================
-- CREATE INDEXES
-- ===========================

-- Users table indexes
CREATE INDEX idx_users_username ON search_poc.users(username);
CREATE INDEX idx_users_email ON search_poc.users(email);

-- Clinical Study table indexes
CREATE INDEX idx_clinical_study_title ON search_poc.clinical_study(title);
CREATE INDEX idx_clinical_study_status ON search_poc.clinical_study(status);
CREATE INDEX idx_clinical_study_phase ON search_poc.clinical_study(phase);

-- Data Products table indexes
CREATE INDEX idx_data_products_study_id ON search_poc.data_products(study_id);
CREATE INDEX idx_data_products_type ON search_poc.data_products(type);
CREATE INDEX idx_data_products_format ON search_poc.data_products(format);

-- Collections table indexes
CREATE INDEX idx_collections_user_id ON search_poc.collections(user_id);

-- Collection Items table indexes
CREATE INDEX idx_collection_items_collection_id ON search_poc.collection_items(collection_id);
CREATE INDEX idx_collection_items_data_product_id ON search_poc.collection_items(data_product_id);

-- Search History table indexes
CREATE INDEX idx_search_history_user_id ON search_poc.search_history(user_id);
CREATE INDEX idx_search_history_query ON search_poc.search_history(query);
CREATE INDEX idx_search_history_category ON search_poc.search_history(category);

-- Scientific Papers table indexes
CREATE INDEX idx_scientific_papers_title ON search_poc.scientific_papers(title);
CREATE INDEX idx_scientific_papers_doi ON search_poc.scientific_papers(doi);
CREATE INDEX idx_scientific_papers_journal ON search_poc.scientific_papers(journal);
CREATE INDEX idx_scientific_papers_publication_date ON search_poc.scientific_papers(publication_date);
CREATE INDEX idx_scientific_papers_citations_count ON search_poc.scientific_papers(citations_count);

-- Data Domain Metadata table indexes
CREATE INDEX idx_data_domain_domain_name ON search_poc.data_domain_metadata(domain_name);
CREATE INDEX idx_data_domain_owner ON search_poc.data_domain_metadata(owner);

-- ===========================
-- GRANT STATEMENTS
-- ===========================

-- Grant for app_user (application user)
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA search_poc TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA search_poc TO app_user;

-- Grant for read_only_user (read-only access)
GRANT SELECT ON ALL TABLES IN SCHEMA search_poc TO read_only_user;


-- Grant for api_user (API access)
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA search_poc TO api_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA search_poc TO api_user;

-- Comments for documentation
COMMENT ON SCHEMA search_poc IS 'Schema for the Search POC application';
COMMENT ON TABLE search_poc.users IS 'User accounts for the application';
COMMENT ON TABLE search_poc.clinical_study IS 'Clinical studies with metadata';
COMMENT ON TABLE search_poc.data_products IS 'Data products related to studies';
COMMENT ON TABLE search_poc.collections IS 'User collections of data products';
COMMENT ON TABLE search_poc.collection_items IS 'Items within user collections';
COMMENT ON TABLE search_poc.search_history IS 'History of user searches';
COMMENT ON TABLE search_poc.scientific_papers IS 'Scientific publications';
COMMENT ON TABLE search_poc.data_domain_metadata IS 'Metadata for data domains'; 