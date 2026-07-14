# Coding Guidelines

## Purpose

This document defines the coding standards for Vikzar AI.

Every contributor must follow these guidelines to ensure consistency, maintainability, readability, and production-quality software.

---

# General Principles

- Write clean code.
- Write readable code.
- Write maintainable code.
- Optimize only after correctness.
- Prefer simplicity over cleverness.

---

# Python Standards

- Python 3.12+
- PEP8 compliant
- Black formatting
- Type hints everywhere
- Docstrings for public classes and functions

Example:

def predict(features: FeatureVector) -> Prediction:
    """Generate injury prediction."""
    ...

---

# Naming Conventions

Variables

snake_case

Functions

snake_case

Classes

PascalCase

Constants

UPPER_CASE

Private methods

_prefix

---

# Project Rules

Never hardcode:

- thresholds
- model paths
- AWS credentials
- ports
- URLs

Everything belongs in app/config.

---

# Architecture Rules

ETL never performs AI.

AI never performs ETL.

FeatureVector is immutable.

Cloud never blocks AI.

Dashboard never blocks AI.

---

# Error Handling

Never ignore exceptions.

Always log exceptions.

Raise meaningful errors.

---

# Logging

Every module should maintain its own logger.

Examples

ETL

AI

Cloud

API

---

# Documentation

Every public function must contain:

Purpose

Parameters

Returns

Exceptions

---

# Testing

Every module must include unit tests.

Critical modules require integration tests.

---

# Performance

Avoid unnecessary copies.

Avoid blocking operations.

Avoid global variables.

---

# Security

Never commit:

- API Keys
- AWS Keys
- Passwords
- Tokens

Use environment variables.

---

# Git

Commit frequently.

Write meaningful commit messages.

Pull before pushing.

---

# Code Reviews

Before merging:

- Code builds
- Tests pass
- Documentation updated
- No debug code