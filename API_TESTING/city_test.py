from tools.cities.apis import *

def main():
    # Initialize class
    print("\n--- Initializing Cities ---")
    cities = Cities()

    print("\n--- Testing load_data() ---")
    cities.load_data()
    print("States loaded:", list(cities.data.keys())[:5])  # show first 5 states

    print("\n--- Testing run(state, origin, dates) ---")
    state = "California"
    origin = "New York"
    dates = ["2025-09-15", "2025-09-20"]
    results = cities.run(state, origin, dates)
    print(f"City search results for state={state}, origin={origin}, dates={dates}:")
    print(results)

    print("\n--- Testing run with invalid state ---")
    invalid_state = "Neverland"
    results = cities.run(invalid_state, origin, dates)
    print(results)


if __name__ == "__main__":
    main()
