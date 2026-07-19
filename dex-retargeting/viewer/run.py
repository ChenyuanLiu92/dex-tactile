import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the D435 vision API service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    uvicorn.run("viewer.backend.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
