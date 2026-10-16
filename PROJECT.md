# F1 Analytics Project

## Purpose

This project showcases data engineering, analytics, and data science skills through a modular Formula 1 analytics system. The project should use strong engineering standards without unnecessary over-engineering, and it should be designed so upstream choices support downstream analysis, storytelling, and repeatable outputs.

Final insights should be usable for portfolio artifacts, GitHub documentation, dashboards, and LinkedIn-style data stories.

## Audience

Primary audience: hiring managers and analytics leaders evaluating technical, analytical, strategic, and communication skills.

Secondary audience: LinkedIn followers, recruiters, and data professionals interested in Formula 1 analytics, practical data storytelling, and reusable analytics workflows.

## Version 1 Goal

Version 1 should prove that the project can ingest Formula 1 data, structure it into clean reusable tables, run basic analysis, and produce one clear insight story.

The first version does not need to be exhaustive, but it should establish the project pattern for data ingestion, data modeling, analysis, documentation, and storytelling.

## Version 1 Success Criteria

Version 1 is successful when the project has:

* A clean repo structure
* A documented project charter
* One ingested F1 dataset
* Reusable cleaned tables
* A basic exploratory analysis
* Validation checks
* One clear insight story that can be turned into a portfolio artifact or LinkedIn post

## Initial Data Direction

Version 1 will start from a free, accessible Formula 1 dataset, with the current expected starting dataset being the Kaggle Formula 1 complete dataset covering 1950 to 2026.

Exact ingestion, storage, refresh, and modeling choices will be decided during project setup. The project should not lock into a data architecture before the dataset structure, quality, and downstream use cases are reviewed.

## Technical Direction

The project should generally showcase:

* Airflow
* Python
* pandas
* SQL
* DuckDB
* dbt
* GitHub
* Tableau
* scikit-learn
* Plotly
* Practical visualization packages that support high-quality analysis and storytelling

The stack may be introduced progressively. Version 1 does not need to implement every tool immediately, but the project should be structured so later sessions can add orchestration, modeling, dashboards, and machine learning without reworking the core foundation.

## Standards

Use modular, readable, reproducible workflows with clear folder structure, documented decisions, naming conventions, validation checks where useful, dashboard-ready outputs, and business-style explanations.

Avoid isolated notebooks, unnecessary complexity, and solutions that solve one step while creating problems downstream.

## Version 1 Non-Goals

Version 1 should avoid:

* Paid APIs
* Large-scale package architecture
* Betting or gambling analysis
* Heavy infrastructure

The initial build should stay lightweight, locally runnable, and focused on proving the end-to-end workflow from data ingestion to reusable tables, basic analysis, and one clear insight story.
