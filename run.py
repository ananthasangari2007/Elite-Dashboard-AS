import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    debug = (os.getenv("FLASK_ENV") or "development").lower() not in {"production", "prod", "staging"}
    app.run(debug=debug, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))