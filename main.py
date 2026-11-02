"""Entry point.   python main.py            -> normal start (data in data/library.db)
                 python main.py --demo     -> same, but loads sample data if the database is empty"""
import argparse

from library import LibrarySystem
from library.cli import ConsoleApp
from library.seed import load_demo_data


def main():
    parser = argparse.ArgumentParser(description="Smart Library Management System")
    parser.add_argument("--db", default="data/library.db", help="path of the database file")
    parser.add_argument("--demo", action="store_true", help="load demo data if the database is empty")
    args = parser.parse_args()
    system = LibrarySystem(args.db)
    try:
        if args.demo and load_demo_data(system):
            print("Demo data loaded.")
        ConsoleApp(system).run()
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted. Data already saved is kept.")
    finally:
        system.close()


if __name__ == "__main__":
    main()
