"""Use cases: load stored data, run the domain engine, save changes.

Services speak domain types (FinancialProfile, Goal, Assumptions, Scenario, ScenarioResult),
so the API and the chat agent never touch database records or do any maths themselves.
Every function takes the SQLAlchemy session to use; write operations commit it.
"""
