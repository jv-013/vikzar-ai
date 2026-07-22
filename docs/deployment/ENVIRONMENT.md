# Environment

## Purpose

This document defines the required software environment for Vikzar AI.

---

# Python

Python Version

3.12+

---

# Operating System

Supported

- Windows
- Linux
- macOS

Development is currently performed on Windows.

---

# Required Packages

Major dependencies include:

- numpy
- pandas
- scipy
- scikit-learn
- xgboost
- lightgbm
- catboost
- pydantic
- fastapi
- uvicorn
- boto3
- joblib

Additional dependencies are listed in requirements.txt.

---

# Development Tools

Recommended

- VS Code
- Git
- GitHub
- ChatGPT Codex

---

# Environment Variables

Examples

AWS_ACCESS_KEY_ID

AWS_SECRET_ACCESS_KEY

AWS_REGION

DATABASE_URL

API_HOST

API_PORT

---

# Virtual Environment

Always use a dedicated virtual environment.

Recommended

python -m venv .venv

Activate before development.

---

# Configuration

All configuration values must remain inside

app/config/

Hardcoded values are prohibited.