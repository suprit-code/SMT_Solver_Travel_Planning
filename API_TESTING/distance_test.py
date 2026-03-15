import numpy as np
from z3 import simplify, Select
from tools.googleDistanceMatrix.apis import *


def extract_z3_array(array, cities=4):
    """
    Extract a multi-index Z3 Array into a human-readable Python dict.
    Each origin-destination index contains simplified values.
    """
    data = {}
    for i in range(cities):
        data[i] = {}
        for j in range(cities):
            try:
                distance = simplify(Select(array, i, j, 0))
                duration = simplify(Select(array, i, j, 1))
                price = simplify(Select(array, i, j, 2))
                length = simplify(Select(array, i, j, 3))
                data[i][j] = {
                    "Distance": distance,
                    "Duration": duration,
                    "Price": price,
                    "Length": length
                }
            except Exception:
                data[i][j] = None
    return data


def main():
    # Initialize API
    distance_api = GoogleDistanceMatrix()

    print("\n--- Testing run_check(origin, destination) ---")
    print(distance_api.run_check("New York", "Boston"))

    print("\n--- Testing run_search(origin) ---")
    print("Possible destinations from New York:")
    print(distance_api.run_search("New York"))

    print("\n--- Testing run(origin, destination) ---")
    print(distance_api.run("New York", "Boston"))

    print("\n--- Testing run_for_evaluation(origin, destination) ---")
    print(distance_api.run_for_evaluation("New York", "Boston"))

    print("\n--- Testing run_for_all_cities(origin, all_cities, cities_list) ---")
    all_cities = ["New York", "Boston", "Chicago", "San Francisco"]
    selected_cities = ["New York", "Chicago"]
    results = distance_api.run_for_all_cities("New York", all_cities, selected_cities)

    # Human-readable Z3 extraction
    print("Results (Z3 arrays, human-readable view):")
    print(extract_z3_array(results, cities=len(all_cities)))

    print("\n--- Testing get_info(info, i, j, key) ---")
    distance_info, length = distance_api.get_info(results, 0, 1, "Distance")
    print("Distance New York → Boston:", distance_info, "| Length:", length)

    print("\n--- Testing get_info(info, i, j, key=Duration) ---")
    duration_info, length = distance_api.get_info(results, 0, 1, "Duration")
    print("Duration New York → Boston:", duration_info, "| Length:", length)


if __name__ == "__main__":
    main()
