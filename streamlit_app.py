"""Trading Desk — Phase 3A Investment Decision Cockpit.

Production release: 3A-COMMITTEE-MACRO-ARCHIVE-2026-11-23.
Entrypoint for Streamlit Cloud, without broker access.
"""

from app.intelligence_dashboard import main


if __name__ == "__main__":
    main()
