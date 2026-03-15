from tools.accommodations.apis import *
import numpy as np
from z3 import simplify, Select  # For Z3 array extraction

def extract_z3_array(array, cities=4, features=4):
    """
    Extracts a multi-index Z3 Array into a human-readable Python dict.
    Each city index contains feature indices and their simplified values.
    """
    data = {}
    for city_idx in range(cities):
        feature_values = {}
        for feat_idx in range(features):
            try:
                val = simplify(Select(array, city_idx, feat_idx))
                feature_values[feat_idx] = val
            except Exception:
                feature_values[feat_idx] = None
        data[city_idx] = feature_values
    return data

def main():
    # Initialize class
    accommodations = Accommodations()

    print("\n--- Testing load_db() ---")
    print(accommodations.load_db())
    print("Database reloaded successfully.")

    print("\n--- Testing run_search(city) ---")
    city = "New York"
    print(f"Room types in {city}:")
    print(accommodations.run_search(city))

    print("\n--- Testing get_type_cities(type) ---")
    room_type = "private room"
    print(f"Cities with {room_type}:")
    print(accommodations.get_type_cities(room_type))

    print("\n--- Testing run(city) ---")
    print(f"Accommodations in {city}:")
    print(accommodations.run(city))

    print("\n--- Testing run_for_all_cities(all_cities, cities) ---")
    all_cities = ["New York", "Boston", "Chicago", "San Francisco"]
    selected_cities = ["New York", "Chicago"]
    results, results_hard = accommodations.run_for_all_cities(all_cities, selected_cities)

    # Human-readable Z3 extraction
    print("\nResults (Z3 arrays, human-readable view):")
    print("Main results:", extract_z3_array(results, cities=len(all_cities), features=4))
    print("Hard constraints:", extract_z3_array(results_hard, cities=len(all_cities), features=4))

    print("\n--- Testing get_info(info, i, key) ---")
    price_list, length = accommodations.get_info(results, 0, 'Price')
    print(f"Price info for city 0: {price_list}, Length: {length}")

    print("\n--- Testing get_info_for_index(price_list, index) ---")
    index = 0
    print(f"Price at index {index}: {accommodations.get_info_for_index(price_list, index)}")



    print("\n--- Testing check_exists(type, accommodation_list, index) ---")
    print("Does 'Private room' exist at index city-0 ?")
    types_list, _ = accommodations.get_info(results_hard, 0, 'Room_types')
    print(accommodations.check_exists('Private room', types_list, 0))


if __name__ == "__main__":
    main()
