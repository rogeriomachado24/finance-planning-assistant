"""Pydantic models for the REST API: request validation, response shape and OpenAPI docs.

Each input model converts itself to a domain object (`to_domain`), and each output model
is built from one (`from_domain`). Money is rounded to the cent here, at the API boundary.
"""
