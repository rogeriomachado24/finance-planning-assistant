"""Load the demo data into the configured database.

python -m app.seed            # refuses if you already entered data
python -m app.seed --reset    # deletes ALL stored data first
"""

import argparse
import sys
from datetime import date

from app.config import Settings, get_settings
from app.db.session import create_db_engine, create_session_factory
from app.services.assumptions import ASSUMPTION_PRESETS
from app.services.demo import DEMO_PROFILE, DEMO_SCENARIOS, load_demo_data
from app.services.errors import ConflictError
from app.services.setup import prepare_database


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__.split("\n")[0])
    parser.add_argument(
        "--reset", action="store_true", help="delete ALL stored data before loading the demo"
    )
    args = parser.parse_args(argv)
    settings = settings or get_settings()

    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        prepare_database(settings.database_url, session_factory)
        with session_factory() as session:
            saved = load_demo_data(session, date.today(), reset=args.reset)
    except ConflictError as exc:
        print(f"Nothing loaded: {exc}. Run with --reset to replace it.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    p, goal = DEMO_PROFILE, saved.goal
    due = f"{goal.target_date.day} {goal.target_date:%b %Y}"  # "1 Jun 2032"
    print(f"Demo data loaded into {settings.database_url}")
    print(
        f"  profile: {p.monthly_net_income:,.0f} EUR income, "
        f"{p.monthly_expenses:,.0f} EUR expenses, {p.liquid_assets:,.0f} EUR saved"
    )
    print(f"  goal: {goal.name}, {goal.target_amount:,.0f} EUR by {due}")
    print(f"  assumption sets: {', '.join(ASSUMPTION_PRESETS)}")
    print(f"  saved scenarios: {', '.join(s.name for s in DEMO_SCENARIOS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
