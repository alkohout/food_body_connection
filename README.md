# Food–Body Connection — Frontend

This repository contains the static frontend for the Food–Body Connection application.

The frontend is hosted on GitHub Pages and communicates with a FastAPI backend via authenticated API calls.

## Project overview

Food–Body Connection is a health analytics application that allows users to:

- Log foods consumed, including quantities and timestamps
- Log symptoms and symptom intensity
- Store structured health data in a relational database
- Analyze relationships between foods and symptoms
- Generate personalized reports highlighting potential trigger foods

## Architecture

Static Frontend (GitHub Pages)
↓ HTTPS (fetch, JWT auth)
FastAPI Backend (AWS)
↓
PostgreSQL Database (AWS RDS)

## Backend

The backend API is implemented using:

- FastAPI (Python)
- SQLAlchemy ORM
- PostgreSQL (AWS RDS)
- JWT-based authentication

Backend repository:
👉 https://github.com/alkohout/food_body_connection

## Status

🚧 The frontend is currently under active development.

Initial functionality will include:
- User authentication
- Food and symptom logging
- Timeline and summary views
- Report generation

## License

MIT

