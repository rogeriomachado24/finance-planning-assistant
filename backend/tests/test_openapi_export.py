from app.export_openapi import OPENAPI_PATH, render_openapi


def test_frontend_api_description_is_up_to_date():
    """Fails when the API changed but the frontend's copy wasn't regenerated. Fix with
    `python -m app.export_openapi` (backend/), then `npm run api:types` (frontend/)."""
    assert OPENAPI_PATH.read_text(encoding="utf-8") == render_openapi()
