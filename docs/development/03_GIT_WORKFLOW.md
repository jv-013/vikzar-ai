# Git Workflow

## Purpose

Defines the Git workflow used by the Vikzar AI team.

---

# Initial Setup

Clone repository

↓

Open project

↓

Install dependencies

↓

Start development

---

# Daily Workflow

git pull

↓

Code

↓

git add .

↓

git commit

↓

git push

---

# Commit Rules

Commit after completing one logical feature.

Do not commit unfinished code unless necessary.

---

# Branch Strategy

Main branch

Stable code only.

Future feature branches may be used if the team grows.

---

# Merge Rules

Pull before push.

Resolve conflicts carefully.

Never overwrite teammate's work.

---

# Repository Ownership

ETL

app/etl

AI

Remaining AI modules

Shared

config

schemas

utils

---

# Good Commit Examples

Added ETL filtering

Implemented Lookup Engine

Created Risk Engine

Integrated Cloud Queue

---

# Bad Commit Examples

update

test

fix

changes

temp

---

# Conflict Resolution

Discuss changes.

Resolve manually.

Retest.

Push updated version.

---

# Backup

Push regularly.

Never rely solely on local copies.