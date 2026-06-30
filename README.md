# NewsNow App

NewsNow is a full‑stack news application built with Django and Django REST Framework. It allows journalists to publish articles, editors to review and approve content, and readers to subscribe to publishers or journalists and receive notifications when new content is approved.

## Project Overview

The platform supports three main roles. Journalists can create and submit articles. Editors can review, approve, and manage articles. Readers can subscribe to journalists or publishers and receive email notifications when approved articles are published. When an editor approves an article, the system sends notification emails to subscribers and logs the approval to an internal API endpoint at /api/approved/.

## Features

- Custom user model with role‑based access (Reader, Editor, Journalist)
- JWT authentication for the REST API
- Article creation, editing, approval, and deletion
- Newsletter creation linking multiple articles
- Reader subscription system for publishers and journalists
- Automatic email notifications using Django signals
- Internal API logging on article approval
- RESTful API built with Django REST Framework
- Automated unit tests for API endpoints
- Responsive UI using Django templates and CSS
- MariaDB database backend

## Tech Stack

Backend: Python 3.x, Django 4.2  
API: Django REST Framework  
Authentication: SimpleJWT  
Database: MariaDB  
Frontend: Django Templates, CSS  
Testing: Django TestCase, DRF APITestCase  
Email: Django console email backend (development)

## Getting Started

### Prerequisites

- Python 3.10 or higher
- MariaDB 10.6 or higher
- pip

## Installation

Clone the repository:

```bash
git clone https://github.com/char-rea/newsapp
cd news_project
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Running with Docker

```bash
docker build -t newsapp .
docker run -p 8000:8000 newsapp
```
Or with Docker Compose:
```bash
docker-compose up --build
```

## Secret Keys / Environment Variables

> Please do NOT commit your `SECRET_KEY` or any passwords.

Create a `.env` file (this is gitignored):
```
SECRET_KEY=your-secret-key-here
DEBUG=True
```

# Database-setup
CREATE DATABASE news_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'news_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON news_db.* TO 'news_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# Update settings.py 
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'news_db',
        'USER': 'news_user',        
        'PASSWORD': 'your_password',  
        'HOST': 'localhost',
        'PORT': '3306',
    }

# Running the application
Apply migrations
python manage.py makemigrations
python manage.py migrate

Create Role Groups
python manage.py setup_groups

Create a Superuser
python manage.py createsuperuser

Start the development server
python manage.py runserver
Visit http://127.0.0.1:8000 in your browser.


# API Auth
Step 1: Get a token
POST /api/token/
Content-Type: application/json

{
    "username": "your_username",
    "password": "your_password"
}

Step 2: Use the Token
Authorization: Bearer eyJ0eXAiOiJKV1Qi...

Step 3: Refresh a Token
POST /api/token/refresh/
Content-Type: application/json

{
    "refresh": "eyJ0eXAiOiJKV1Qi..."
}


# Running Tests
The test suite covers all required areas:

Authenticated access per role
Reader subscribed content
Journalist can create articles
Editor can approve and delete
Newsletter behaviour
Signal logic with mocking

python manage.py test news

Expected output: 
Found 18 tests...
.................
----------------------------------------------------------------------
Ran 18 tests in 4.085s

OK

Created by Charlotte Hill
