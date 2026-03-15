from tools.transits.apis import Transits
from z3 import simplify, Select

def main():
    transits = Transits()

    print("\n--- Testing load_db() ---")
    print(transits.load_db())
    print("Database reloaded successfully.")

    # Test by city
    print("\n--- By city ---")
    print(transits.run("New York"))  # replace with a valid city

    # Test by city + PoI
    print("\n--- By city + PoI ---")
    print(transits.run("New York", "Statue of Liberty"))

if __name__ == "__main__":
    main()
