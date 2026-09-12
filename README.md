# FixMate Backend

A production-oriented REST API backend for **FixMate**, a service marketplace platform that connects customers with service providers.

Customers can create service requests, providers can submit offers, and customers can accept an offer to create a booking. The platform also supports reviews, provider profiles, authentication, filtering, search, and API documentation.

## Features

* JWT-based authentication
* Customer and service provider roles
* Provider profiles and verification
* Service categories and service areas
* Service request creation and management
* Provider offers with validation
* Offer acceptance and booking creation
* Booking lifecycle management
* Customer and provider reviews
* Image uploads for profiles, requests, and reviews
* Role-based permissions
* Filtering, searching, ordering, and pagination
* PostgreSQL database support
* Firebase integration for Google authentication
* API validation and business rules
* Automated API tests
* Swagger / OpenAPI documentation
* ReDoc API documentation

## Core Flow

```text
Customer
   │
   ▼
Service Request
   │
   ▼
Provider Offers
   │
   ▼
Accept Offer
   │
   ▼
Booking
   │
   ▼
Complete Service
   │
   ▼
Review
```

## Tech Stack

* **Python**
* **Django**
* **Django REST Framework**
* **PostgreSQL**
* **Simple JWT**
* **Firebase Authentication**
* **drf-spectacular**
* **Swagger / OpenAPI**
* **ReDoc**

## API Documentation

Once the project is running, API documentation is available at:

* Swagger UI: `/api/docs/`
* ReDoc: `/api/redoc/`
* OpenAPI Schema: `/api/schema/`

Swagger supports JWT authentication through the **Authorize** button.

## Project Structure

```text
FixMate Backend/
├── api/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── permissions.py
│   ├── urls.py
│   └── tests/
├── firebase/
├── config/
├── manage.py
├── requirements.txt
└── .gitignore
```

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file and add the required project configuration, including your PostgreSQL database credentials and other secret values.

### 5. Apply migrations

```bash
python manage.py migrate
```

### 6. Run the development server

```bash
python manage.py runserver
```

The API will then be available locally.

## Testing

Run the test suite with:

```bash
python manage.py test
```

## Status

**Phase 1 — Backend: Completed**

The backend currently provides the core FixMate marketplace functionality, authentication, business logic, validation, testing, and documented REST APIs.

## Author

**Syed Hassan Askari**

**hassanaskarin2361@gmail.com**
