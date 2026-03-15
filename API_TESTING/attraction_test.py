from tools.attractions.apis import *
import numpy as np
from z3 import simplify, Select  # For Z3 array extraction

def extract_z3_array(array, cities=4):
    """
    Extracts a Z3 Array into a human-readable Python dict.
    Each city index maps to its attraction count (or -1 if none).
    """
    data = {}
    for city_idx in range(cities):
        try:
            val = simplify(Select(array, city_idx))
            data[city_idx] = val
        except Exception:
            data[city_idx] = None
    return data


def main():
    # Initialize class
    attractions = Attractions()

    print("\n--- Testing load_db() ---")
    print(attractions.load_db())
    print("Database reloaded successfully.")

    print("\n--- Testing run(city) ---")
    city = "New York"
    print(f"Attractions in {city}:")
    print(attractions.run(city))

    print("\n--- Testing run_for_all_cities(all_cities, cities) ---")
    all_cities = ["New York", "Boston", "Chicago", "San Francisco"]
    selected_cities = ["New York", "Chicago"]
    results = attractions.run_for_all_cities(all_cities, selected_cities)

    # Human-readable Z3 extraction
    print("\nResults (Z3 arrays, human-readable view):")
    print("Main results:", extract_z3_array(results, cities=len(all_cities)))

    print("\n--- Testing get_info(info, i) ---")
    city_index = 0
    length = attractions.get_info(results, city_index)
    print(f"Number of attractions for {all_cities[city_index]}:", length)

    print("\n--- Testing get_info_for_index(price_list, index) ---")
    # Here we just re-use results as price_list placeholder
    index = 0
    print(f"Attraction info at index {index}: {attractions.get_info_for_index(results, index)}")

    print("\n--- Testing attraction_in_which_city(...) ---")
    arrives = [20.0, 15.0, 22.5]
    origin = 0
    cities = [1, 2, 3]
    departure_dates = [0, 1, 2]
    days = 3
    result = attractions.attraction_in_which_city(arrives, origin, cities, departure_dates, days)
    print("Attraction visit sequence (Z3 expressions):", result)


if __name__ == "__main__":
    main()
