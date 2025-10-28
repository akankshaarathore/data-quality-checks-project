# COVID-19 Counties Data Quality Analysis

A comprehensive data quality framework for analyzing COVID-19 county-level healthcare, demographic, and socioeconomic data across US counties.

## 📋 Overview

This project implements an intelligent data quality pipeline that processes 348 columns of county-level data, automatically selects the 30 most relevant columns using a weighted scoring algorithm, and validates data integrity across 7 quality dimensions with 53+ automated checks.

**Dataset**: COVID-19 US Counties (Kaggle)  
**Records**: 3,142+ counties  
**Quality Checks**: 53 validations across 7 dimensions

---

## 🎯 Problem Statement

Large-scale public health datasets often suffer from:
- Missing or incomplete data in critical fields
- Inconsistent data formats across sources
- Unrealistic or impossible values
- Broken relationships between related fields
- High dimensionality making quality assessment difficult

**Our Solution**: An automated, scalable data quality framework that intelligently prioritizes columns and systematically validates data integrity.

---

## 🏗️ Architecture

### Pipeline Phases

1. **Infrastructure Setup** - Database and API configuration
2. **Data Acquisition** - Automated Kaggle dataset download
3. **Data Loading** - PostgreSQL database ingestion
4. **Data Profiling** - Intelligent column selection (348 → 30)
5. **Quality Checks** - Multi-dimensional validation
6. **Visualization** - Interactive Streamlit dashboard

---

## 🔍 Intelligent Column Selection

### Why Column Selection Matters

With 348 columns, comprehensive quality checks would be:
- Computationally expensive and time-consuming
- Difficult to interpret and act upon
- Often redundant (many columns have low utility or high correlation)

### Multi-Criteria Scoring Algorithm

We rank all 348 columns using weighted criteria:

| Criterion | Rationale |
|-----------|-----------|
| **Completeness** | Columns with fewer NULLs are more reliable |
| **Uniqueness** | High cardinality indicates richer information |
| **Data Type** | Numeric fields enable better quality checks |
| **Domain Relevance** | Critical for COVID-19 analysis |

### Domain Categories & Importance

- **Identifiers**  - FIPS codes, area names
- **Population Base**  - Population estimates
- **Demographics**  - Vulnerable populations (age 65+, 85+)
- **Healthcare Capacity**  - ICU beds, hospitals, physicians
- **Socioeconomic**  - Income, poverty, unemployment
- **Geographic**  - Density, land area

**Result**: Top 30 columns selected for comprehensive quality validation

---

## ✅ Data Quality Checks

#### 1. Completeness (19 checks)
**What**: Data is present and not missing  
**Why It Matters**: Missing ICU beds or population data prevents accurate resource planning and risk assessment  
**Severity Levels**:
- **HIGH**: FIPS codes, population, ICU beds, hospitals
- **MEDIUM**: Healthcare workforce, socioeconomic indicators

#### 2. Uniqueness (2 checks)
**What**: No duplicate records where uniqueness is expected  
**Why It Matters**: Duplicate FIPS codes indicate data loading errors and invalidate aggregations  
**Key Checks**: Primary key validation, area name duplication

#### 3. Conformity (4 checks)
**What**: Data follows expected formats and standards  
**Why It Matters**: Invalid FIPS formats (non-5-digit) break geographic mapping and data joins  
**Key Checks**: FIPS format validation, non-negative constraints

#### 4. Accuracy (10 checks)
**What**: Data reflects realistic real-world values  
**Why It Matters**: Unrealistic values (e.g., elderly population > total population) corrupt pandemic modeling  
**Key Checks**:
- Population logic (age hierarchies, subset validation)
- Healthcare reasonableness (ICU beds < population, hospital counts < 1000)
- Percentage bounds (unemployment, poverty: 0-100%)
- Economic sanity (median income > $10,000)

#### 5. Integrity (2 checks)
**What**: Relationships between fields are valid  
**Why It Matters**: Ensures internal consistency and detects calculation errors  
**Key Checks**:
- Gender sum validation (male + female = total)
- Age hierarchy (85+ subset of 65+)

#### 6. Consistency (1 check)
**What**: Derived values match calculation formulas  
**Why It Matters**: Validates data transformation accuracy  
**Key Check**: Population density = population / land area (±1 tolerance)

#### 7. Validity (2 checks)
**What**: Values are within acceptable business domains  
**Why It Matters**: Zero/negative land area is geographically impossible  
**Key Checks**: Positive land area, positive median income

### Severity Classification

**HIGH** - Critical issues compromising core analysis (missing FIPS, invalid population)  
**MEDIUM** - Significant issues affecting specific analyses (missing workforce data)  
**LOW** - Minor inconsistencies with limited impact (small calculation differences)

---

## 🛠️ Technology Stack

- **Database**: PostgreSQL 14+
- **Data Processing**: Python 3.8+, pandas
- **API Integration**: Kaggle API
- **Visualization**: Streamlit, Plotly
- **Version Control**: Git

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 14+
- Kaggle account with API credentials

### Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Configure PostgreSQL database
3. Set environment variables in `.env` file
4. Place Kaggle API token in `~/.kaggle/kaggle.json`

### Run Pipeline
1. **Download data**: `python data_ingestion.py`
2. **Profile columns**: `python data_profiler.py`
3. **Run quality checks**: `python data_quality_checks.py`
4. **Launch dashboard**: `streamlit run dq_dashboard.py`

---


## 📁 Project Structure

```
covid_data_analysis/
├── data_ingestion.py              # Kaggle download automation
├── data_profiler.py               # Column selection algorithm
├── data_quality_checks.py         # DQ validation engine
├── dq_dashboard.py                # Streamlit visualization
├── generate_flowchart.py          # Documentation generator
├── selected_columns_for_dq.txt    # Top 30 columns
├── dq_results.csv                 # Quality check results
└── README.md                      # This file
```

---

## 📊 Results Summary

View the interactive dashboard for current quality metrics including:
- Overall pass/fail rates
- Checks by severity level
- Top data quality issues
- Detailed check results
- Actionable recommendations

---

- **Dataset**: Kaggle COVID-19 US Counties Dataset
- **Data Sources**: US Census Bureau, AAMC, HRSA
- **Inspiration**: ISO 8000 Data Quality Standards
