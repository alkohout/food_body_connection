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
# Allergen & Symptom Tracking and Analysis App

## Overview

This project is a full‑stack allergen and symptom tracking application designed to help users identify likely food (or other) allergens associated with adverse symptoms. Users log allergen exposures and symptoms over time, and the system applies statistical analysis and machine‑learning models to estimate which allergens are most strongly associated with symptom onset.

The goal of the project is **decision support**, not diagnosis: to surface patterns that may not be obvious to users, and to present them in an interpretable, user‑friendly way.

---

## Key Features

### 1. Logging & Data Collection

* Log **allergen exposure events** (food items, quantities, units, timestamps).
* Log **symptom events** (symptom type, severity, timestamps).
* Data stored in a relational database via SQLAlchemy models.
* Designed to handle **frequent exposure logging** with relatively **rare symptom events**.

### 2. Time‑Aware Feature Engineering

* Exposure–symptom relationships are evaluated using configurable **time windows** (e.g. allergen consumed within 24 hours prior to symptom).
* Construction of supervised learning datasets (`X`, `y`) by:

  * Aligning allergen events with subsequent symptom events
  * Encoding exposure presence/absence (and optionally dose)
  * Aggregating across users or analyzing per‑user

### 3. Statistical & Machine Learning Analysis

* Supervised classification models to estimate:

  * Probability an allergen is associated with a symptom
  * Relative importance of allergens
* Current approaches include:

  * Logistic regression
    - Binary target ( symptom occurred (1) versus not (0))
    - Can calculate odds ratio (exponential of coefficient) which is easily interpretable
    - Works with categorical data
    - Stable with small and imbalanced datasets 
    - L1 or L2 used to prevent overfitting
    - Fast computation
  * Nested Cross Validation
    - Dataset is relatively small
    - Performance metrics will be shown to users
    - Require robust uncertainty estimates
    - Avoid dependence on a single split

* Model evaluation using:

  * ROC AUC
  * Symptom recall
  * Bootstrapping / confidence intervals

### 4. Interpretability & Visualisation

* Correlation heatmaps between allergens and symptoms
* Ranked allergen lists by likelihood or importance
* Simple visual indicators (green / orange / red) for model confidence or risk level
* Designed for **non‑technical end users**

### 5. Web Interface & API

* Backend built with **FastAPI**
* REST endpoints for:

  * Logging data
  * Triggering analyses
  * Returning metrics and plots
* Frontend renders plots and summaries for easy interpretation

---

## Project Structure

```text
app/
├── analysis/
│   ├── get_xy.py                 # Feature/label construction
│   ├── supervised_classification.py
│   └── ...
├── data/
│   └── analysis_data.py          # Data loading helpers
├── models/
│   └── table_class.py            # SQLAlchemy ORM models
├── schemas/
│   └── analyse.py                # Pydantic schemas for analysis
├── database.py                   # DB session and engine
└── main.py                       # FastAPI entry point
```

---

## Data Model (Conceptual)

### Core Entities

* **User** – application user
* **Allergen** – identifiable allergen (e.g. dairy, eggs, nuts)
* **AllergenLog** – timestamped exposure events
* **Symptom** – symptom type (e.g. headache, nausea)
* **SymptomLog** – timestamped symptom events

Relationships are structured to allow many exposures and symptoms per user over time.

---

## Feature Engineering Strategy

### Problem Framing

* Symptoms are **binary or categorical outcomes**
* Allergen exposure is a **sparse, time‑dependent signal**

### Exposure Windows

* For each symptom event, allergens are marked as:

  * `1` if consumed within a defined time window (e.g. 24 hours)
  * `0` otherwise

### Dataset Construction

* `X`: allergen exposure matrix
* `y`: symptom presence / absence
* Supports:

  * Per‑symptom modelling
  * Aggregated symptom groups

---

## Modelling & Evaluation

### Models

* Logistic Regression (baseline, interpretable)
* Random Forest (non‑linear relationships)

### Metrics

* **ROC AUC** – overall discriminative power
* **Recall** – ability to correctly identify symptom events
* **Bootstrap confidence intervals** – robustness under limited data

### Data Limitations

* Designed to work with:

  * Small datasets
  * Class imbalance (many exposures, few symptoms)
* Results improve as longitudinal data accumulates

---

## Design Principles

* **Interpretability first** – users must understand outputs
* **Time‑aware analysis** – symptoms are delayed responses
* **Incremental learning** – models improve as data grows
* **Health‑adjacent, not medical** – no diagnostic claims

---

## Intended Use

* Identify *candidate* allergens to investigate further
* Support elimination diets or tracking strategies
* Provide insights to discuss with healthcare professionals

---

## Limitations & Caveats

* Correlation ≠ causation
* Confounding factors (stress, sleep, illness) not yet modelled
* Small sample sizes can inflate uncertainty
* Results should not be used for medical diagnosis

---

## Future Work

* Multi‑lag exposure modelling (e.g. 6h / 12h / 24h / 48h)
* Symptom severity regression
* Unsupervised pattern discovery
* User‑specific vs population‑level models
* Improved visual explanations

---

## Status

This project is under active development and experimentation, with a focus on robust data modelling, interpretable analytics, and user‑centred design.

