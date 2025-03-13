# BioMed Search Service

A comprehensive biomedical search service API designed to streamline scientific data discovery and management, with advanced search interaction capabilities.

## Features

- Advanced multi-collection search across:
  - Clinical Studies
  - Scientific Papers
  - Data Domains
- Rich filtering capabilities:
  - Scientific Papers:
    - Journal-based filtering
    - Publication date ranges (last week/month/year)
    - Citation count ranges
  - Clinical Studies:
    - Study status
    - Trial phase
    - Medical categories
- Dynamic search suggestions
- User collections management
- Comprehensive search history tracking
- OAuth 2.0 Authentication

## Requirements

- Python 3.11 or higher
- PostgreSQL 14 or higher
- pip (Python package installer)

## Local Setup

### 1. OAuth Configuration

1. Set up OAuth 2.0 credentials in Google Cloud Console:
   - Go to https://console.cloud.google.com/apis/credentials
   - Create a new OAuth 2.0 Client ID
   - Add the following redirect URI for local development:
     ```
     http://localhost:5000/auth/callback
     ```
   - Save your Client ID and Client Secret

2. Create a `.env` file in the project root:
   ```bash
   # OAuth Configuration
   OAUTH_ISSUER=https://accounts.google.com
   OAUTH_CLIENT_ID=your_client_id
   OAUTH_CLIENT_SECRET=your_client_secret

   # Database configuration
   DATABASE_URL=postgresql://localhost/biomed_search

   # Session secret (change this to a secure random string)
   SESSION_SECRET=your-secret-key-here
   ```

### 2. Database Setup

1. Create the database:
```bash
createdb biomed_search
```

2. The tables will be automatically created when you first run the application, but you can populate sample data:
```bash
python populate_db.py
```

This will create:
- Sample users
- Clinical studies with various phases and statuses
- Scientific papers with varied journals and citation counts
- Data products and collections

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

When you first access any page, you'll be automatically redirected to Google's OAuth login page. After successful authentication, you'll be redirected back to your original destination.

## API Documentation

The API documentation is available at:
- Swagger UI: http://localhost:5000/docs
- ReDoc: http://localhost:5000/redoc

## Common Issues & Solutions

### Database Connection Issues

1. **Can't connect to PostgreSQL**
   - Check if PostgreSQL is running: `pg_isready`
   - Verify database exists: `psql -l`
   - Ensure DATABASE_URL in .env is correct

2. **Permission Issues**
   - Check PostgreSQL user permissions: `psql -l`
   - If needed, grant permissions: `psql -c "GRANT ALL PRIVILEGES ON DATABASE biomed_search TO your_username;"`

### OAuth Configuration Issues

1. **redirect_uri_mismatch Error**
   - Verify the redirect URI in Google Cloud Console matches exactly:
     - Development: `http://localhost:5000/auth/callback`
     - Production: `https://your-domain.com/auth/callback`
   - Check that the OAUTH_* environment variables are correctly set
   - Ensure your Google OAuth credentials are properly configured

2. **Authentication Failed**
   - Check Google Cloud Console for error logs
   - Verify that the required scopes (openid, profile, email) are enabled
   - Ensure your OAuth application is properly configured and enabled

### Port Already in Use

If port 5000 is already in use:
1. Find the process: `lsof -i :5000`
2. Stop the process: `kill -9 <PID>`

## Support

For issues and questions, please create an issue in the repository or contact the development team.