
## Food-Body Connection Overview

This project is a full‑stack allergen and symptom tracking application designed to help users identify likely food (or other) allergens associated with adverse symptoms. Users log allergen exposures and symptoms over time, and the system applies statistical analysis and supervised machine‑learning models to estimate which allergens are most strongly associated with symptom onset.

The goal of the project is **decision support**, not diagnosis: to surface patterns that may not be obvious to users, and to present them in an interpretable, user‑friendly way.

Essentially, the Food–Body Connection is a health analytics application that allows users to:
- Log foods consumed, including quantities and timestamps
- Log symptoms and symptom intensity
- Store structured health data in a relational database
- Analyze relationships between allergens and symptoms
- Generate personalized reports highlighting potential trigger foods
- Identify *candidate* allergens to investigate further
- Support elimination diets or tracking strategies
- Provide insights to discuss with healthcare professionals

## Key Features

### Logging & Data Collection

* Log **allergen exposure events** (allergens, quantities, units, timestamps).
* Log **symptom events** (symptom type, severity, timestamps).
* Data stored in a relational database via SQLAlchemy models.
* Designed to handle **frequent exposure logging** with relatively **rare symptom events**.

### Time‑Aware Feature Engineering

* Exposure–symptom relationships are evaluated using configurable **time windows** (e.g. allergen consumed within 24 hours prior to symptom).
* Construction of supervised learning datasets (`X`, `y`) by:
  * Aligning allergen events with subsequent symptom events
  * Encoding exposure presence/absence (and optionally dose)

### Statistical & Machine Learning Analysis
#### Design Principles
* **Interpretability first** – users must understand outputs
* **Time‑aware analysis** – symptoms are delayed responses
* **Incremental learning** – models improve as data grows
* Designed to work with:
  * Small datasets
  * Class imbalance (many exposures, few symptoms)

* Supervised classification models to estimate:
  * Probability an allergen is associated with a symptom
  * Relative importance of allergens

#### Logistic Regression
- **Purpose:** Estimate the **association between an allergen and symptom occurrence**.  
- **Target:** Binary outcome — symptom occurred (1) or not (0).  

- **Key features:**
  - Coefficients can be exponentiated to obtain **odds ratios**, providing an intuitive measure of effect size.  
  - Relatively stable for **small or imbalanced datasets** due to:
    - its **low-variance parametric form**
    - **regularization (L1 or L2)** to reduce overfitting and mitigate collinearity  
    - **class weighting**, when necessary, to reduce bias from class imbalance  
    - **nested cross-validation** to estimate performance metrics and quantify uncertainty in small samples  
  - Fast computation enables rapid iteration, model testing, and timely outputs for users.  

- **Use case:** Identify which allergens are significantly associated with symptoms and quantify the strength of those associations.
* Model evaluation using:
  * ROC AUC
  * Symptom recall
  * Bootstrapping / confidence intervals

#### Fisher Exact Test
- **Purpose:** Test for **association between categorical variables** when sample sizes are small.  
- **Key features:**
  - Exact test for contingency tables, avoiding approximations.  
  - Provides **p-values** for significance of association between an allergen and symptom occurrence.  
  - Works well with **rare events or imbalanced data**.  
- **Use case:** Confirm associations suggested by logistic regression in **small datasets** or when counts are low.
* Model evaluation using:
  * p-value

#### Ordinal Logistic Regression (Ordered Logit)

- **Purpose:** Estimate the **dose–response relationship between allergen exposure volume and symptom severity**.  
- **Target:** **Ordinal outcome** — peak symptom intensity level (e.g., 0, 1, 2, 3) within a specified post‑exposure time window.

- **Key features:**
  - Explicitly models **ordered symptom intensity levels**, preserving clinically meaningful rank information that would be lost in binary models.
  - Estimates a **single monotonic effect** of allergen volume across all symptom thresholds via the **proportional odds assumption**.
  - Coefficients can be exponentiated to produce **odds ratios**, interpreted as:
    > the change in odds of experiencing a *higher* symptom intensity level per unit increase in allergen volume (scaled).
  - Uses **maximum likelihood estimation**, providing:
    - parameter estimates  
    - standard errors  
    - confidence intervals for odds ratios  
  - Volume standardization improves:
    - numerical stability  
    - interpretability of effect sizes  
    - comparability across allergens with different exposure scales.
  - Well‑suited for **small to moderate datasets** where symptom intensity is recorded discretely and repeatedly.

- **Use case:**  
  Quantify whether **larger allergen exposures are associated with more severe symptoms**, and assess the strength and uncertainty of that dose–response relationship.

- **Model evaluation / reporting using:**
  - **Odds ratio with 95% confidence interval** for exposure volume  
  - Direction and strength of effect (risk‑increasing vs protective)  
  - Visual diagnostics via:
    - violin plots of exposure volume by symptom intensity  
    - annotated effect size summaries  
  - Sensitivity analysis across different **post‑exposure lag windows**

### Interpretability & Visualisation
* Simple visual indicators (green / orange / red) for model confidence or risk level
* Designed for **non‑technical end users**

## Limitations & Caveats
* Correlation ≠ causation
* Confounding factors (stress, sleep, illness) not yet modelled
* Small sample sizes can inflate uncertainty
* Results should not be used for medical diagnosis

## Architecture
Static Frontend (GitHub Pages)
↓ HTTPS (fetch, JWT auth)
FastAPI Backend (AWS)
↓
PostgreSQL Database (AWS RDS)

### Backend
The backend API is implemented using:
- FastAPI (Python)
- SQLAlchemy ORM
- PostgreSQL (AWS RDS)
- JWT-based authentication
* REST endpoints for:
  * Logging data
  * Triggering analyses
  * Returning metrics and plots

### Frontend
 - The frontend is hosted on GitHub Pages and communicates with a FastAPI backend via authenticated API calls.
 - It renders plots and summaries for easy interpretation

---

### Project Structure
```
├── app/
│   ├── analysis/             # Data analysis, statistics, ML, and time-series processing
│   ├── api/
│   │   └── routes/           # FastAPI route handlers (auth, users, logs, analytics, plots)
│   ├── core/                 # Security, JWT handling, core app logic
│   ├── data/                 # Data access and analysis helpers
│   ├── models/               # SQLAlchemy models and ML models
│   ├── schemas/              # Pydantic schemas for request/response validation
│   ├── utils/                # Shared utilities and preprocessing helpers
│   ├── config.py             # Application configuration
│   ├── database.py           # Database connection and session management
│   ├── main.py               # FastAPI application entry point
│   └── models.py             # Model imports/registry
├── logs/                     # Application and server logs
├── scripts/                  # Database setup and data generation scripts
├── docs/
│   ├── assets/               # Images and static documentation assets
│   ├── js/                   # Frontend JavaScript (dashboard, API calls)
│   └── static/               # Static HTML and CSS files
├── frontend/                 # Frontend-related files and certificates
├── README.md                 # Project documentation
```

#### Key Concepts
- **Backend**: FastAPI application handling authentication, data logging, analytics, and predictions
- **Analysis**: Statistical analysis, EDA, ML classification, and time‑series modeling
- **Models**: Database schema definitions and trained ML models
- **Scripts**: Utilities for database initialization and synthetic data generation
- **Docs / Frontend**: Dashboard UI, static assets, and project documentation
---

### Database Schema Overview

The database tracks user-defined allergens and symptoms, along with timestamped
exposure and symptom events over time.

#### Tables
**users - Application users. **
| Column | Type | Key | Description |
|------|------|-----|-------------|
| user_id | Integer | PK | Unique user identifier |
| email | String |  | User email (unique) |
| password_hash | String |  | Hashed password |
| created_at | DateTime (UTC) |  | Account creation time |
---

**allergen User - defined allergens (e.g. dairy, eggs). **
| Column | Type | Key | Description |
|------|------|-----|-------------|
| allergen_id | Integer | PK | Unique allergen ID |
| user_id | Integer | FK → users.user_id | Allergen owner |
| allergen_name | String |  | Allergen name |

Constraint:  
- UNIQUE (user_id, allergen_name)
---

**unit - Units used to quantify allergen exposure.**
| Column | Type | Key | Description |
|------|------|-----|-------------|
| unit_id | Integer | PK | Unit identifier |
| unit_name | String |  | Unit name (e.g. grams, cups) |
| unit_conversion | Integer |  | Conversion factor |
---

**allergen_log - Logged allergen exposure events.**
| Column | Type | Key | Description |
|------|------|-----|-------------|
| allergen_log_id | Integer | PK | Exposure log ID |
| user_id | Integer | FK → users.user_id | User |
| allergen_id | Integer | FK → allergen.allergen_id | Allergen |
| date_time | DateTime (UTC) |  | Exposure time |
| quantity | Float |  | Amount consumed |
| unit_id | Integer | FK → unit.unit_id | Measurement unit |
---

**symptom - User-defined symptoms (e.g. headache, nausea).**
| Column | Type | Key | Description |
|------|------|-----|-------------|
| symptom_id | Integer | PK | Symptom ID |
| user_id | Integer | FK → users.user_id | Symptom owner |
| symptom_name | String |  | Symptom name |
| symptom_group | String |  | Optional category |

Constraint:  
- UNIQUE (user_id, symptom_name)
---

**symptom_log - Logged symptom events.**
| Column | Type | Key | Description |
|------|------|-----|-------------|
| symptom_log_id | Integer | PK | Symptom log ID |
| user_id | Integer | FK → users.user_id | User |
| symptom_id | Integer | FK → symptom.symptom_id | Symptom |
| date_time | DateTime (UTC) |  | Event time |
| symptom_intensity | Integer |  | Severity (0–3) |

Constraint:  
- CHECK (symptom_intensity BETWEEN 0 AND 3)
---

#### Notes
- All timestamps are stored in UTC
- Allergens and symptoms are scoped per user
- Users may log multiple exposures and symptoms over time

## Future Work
### Planned Analysis Enhancements
- Identify and analyze recurring patterns in symptom occurrence
- Enable analysis across user‑selected date ranges
- Support logging of multiple allergens and symptoms within a single event
- Data Management Improvements

### Introduce a dedicated Food table with automatic allergen assignment
- Add an editable data view allowing users to modify or delete logged entries
- Provide access to raw data for greater transparency and control

### Reporting & Sharing
- Enable optional email delivery of generated reports

### Architecture & Scalability
- Migrate to an alternative system architecture to support long‑term growth and scalability

