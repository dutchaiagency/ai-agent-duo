# Task Brief

## Goal

Fix the CSV import script so rows with empty optional columns are accepted.

## Context and links

- Repository: https://github.com/example/project
- Failing command: `python scripts/import_customers.py samples/customers.csv`
- Current error: `ValueError: expected 8 columns`

## Done criteria

- Empty optional columns no longer crash the importer.
- Existing import behavior remains unchanged for complete rows.
- Add or update a targeted test for the edge case.
- Provide a short note explaining the fix.

## Deadline

2026-05-02

## Budget

60 USDC
