
## Food-Body Connection Overview

This project is a full‑stack allergen and symptom tracking application designed to help users identify likely food (or other) allergens associated with adverse symptoms. Users log allergen exposures and symptoms over time, and the system applies statistical analysis and supervised machine‑learning models to estimate which allergens are most strongly associated with symptom onset.

The goal of the project is **decision support**, not diagnosis: to surface patterns that may not be obvious to users, and to present them in an interpretable, user‑friendly way.

Essentially, the Food–Body Connection is a health analytics application that allows users to:
- Log foods consumed, including quantities and timestamps
- Log symptoms and symptom intensity
- Store structured health data in a relational database
- Analyze relationships between allergens and symptoms
- Generate personalized reports highlighting potential trigger foods

## Key Features

### 1. Logging & Data Collection

* Log **allergen exposure events** (allergens, quantities, units, timestamps).
* Log **symptom events** (symptom type, severity, timestamps).
* Data stored in a relational database via SQLAlchemy models.
* Designed to handle **frequent exposure logging** with relatively **rare symptom events**.

### 2. Time‑Aware Feature Engineering

* Exposure–symptom relationships are evaluated using configurable **time windows** (e.g. allergen consumed within 24 hours prior to symptom).
* Construction of supervised learning datasets (`X`, `y`) by:
  * Aligning allergen events with subsequent symptom events
  * Encoding exposure presence/absence (and optionally dose)

### 3. Statistical & Machine Learning Analysis

* Supervised classification models to estimate:
  * Probability an allergen is associated with a symptom
  * Relative importance of allergens
* Current approaches include:

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

### 4. Interpretability & Visualisation
* Simple visual indicators (green / orange / red) for model confidence or risk level
* Designed for **non‑technical end users**

### 5. Architecture

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
* REST endpoints for:

  * Logging data
  * Triggering analyses
  * Returning metrics and plots

## Frontend
The frontend is hosted on GitHub Pages and communicates with a FastAPI backend via authenticated API calls.
It renders plots and summaries for easy interpretation

---

## Project Structure

```text
app/
├── analysis/
│   ├── get_xy.py                 # Feature/label construction
│   ├── supervised_classification.py
│   └── ...
├── api/
|   ├── routes
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
* **Unit** - unit used to define quantity in allergen log (e.g. cups, litres )

Relationships are structured to allow many exposures and symptoms per user over time.


### Data Limitations

* Designed to work with:

  * Small datasets
  * Class imbalance (many exposures, few symptoms)
* Results improve as longitudinal data accumulates

## Design Principles

* **Interpretability first** – users must understand outputs
* **Time‑aware analysis** – symptoms are delayed responses
* **Incremental learning** – models improve as data grows
* **Health‑adjacent, not medical** – no diagnostic claims

## Intended Use

* Identify *candidate* allergens to investigate further
* Support elimination diets or tracking strategies
* Provide insights to discuss with healthcare professionals

## Limitations & Caveats

* Correlation ≠ causation
* Confounding factors (stress, sleep, illness) not yet modelled
* Small sample sizes can inflate uncertainty
* Results should not be used for medical diagnosis

## Future Work

* Unsupervised pattern discovery
* Improved visual explanations
* Improved logging tools

## Status

This project is under active development and experimentation, with a focus on robust data modelling, interpretable analytics, and user‑centred design.

