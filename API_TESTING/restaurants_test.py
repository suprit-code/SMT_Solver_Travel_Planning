from tools.restaurants.apis import Restaurants
from z3 import simplify, Select


def extract_z3_array(array, cities=4, features=2):
    """
    Extract Z3 Array into a human-readable dictionary.
    Handles multi-index selects (e.g., city, feature).
    """
    data = {}
    for city_idx in range(cities):
        feature_values = {}
        for feat_idx in range(features):
            try:
                feature_values[feat_idx] = simplify(Select(array, city_idx, feat_idx))
            except Exception:
                feature_values[feat_idx] = None
        data[city_idx] = feature_values
    return data


def extract_z3_cuisines(array, cities=4, cuisines=7):
    """
    Extract restaurant cuisines Z3 Array into a readable dictionary.
    """
    cuisines_list = ['Chinese', 'American', 'Italian', 'Mexican', 'Indian', 'Mediterranean', 'French']
    data = {}
    for city_idx in range(cities):
        cuisine_flags = {}
        for cuisine_idx in range(cuisines):
            try:
                cuisine_flags[cuisines_list[cuisine_idx]] = simplify(
                    Select(array, city_idx, cuisine_idx)
                )
            except Exception:
                cuisine_flags[cuisines_list[cuisine_idx]] = None
        data[city_idx] = cuisine_flags
    return data


def main():
    # Initialize class
    restaurants = Restaurants()

    print("\n--- Testing load_db() ---")
    restaurants.load_db()
    print("Database reloaded successfully.")

    print("\n--- Testing run(city) ---")
    city = "New York"
    print(f"Restaurants in {city}:")
    print(restaurants.run(city))

    print("\n--- Testing run_for_all_cities(all_cities, cities) ---")
    all_cities = ["New York", "Boston", "Chicago", "San Francisco"]
    selected_cities = ["New York", "Chicago"]
    results, results_cuisines = restaurants.run_for_all_cities(all_cities, selected_cities)

    print("\nResults (Z3 arrays, human-readable view):")
    print("Main results:", extract_z3_array(results, cities=len(all_cities), features=2))
    print("Cuisines info:", extract_z3_cuisines(results_cuisines, cities=len(all_cities)))

    print("\n--- Testing get_info(info, i, key) ---")
    price_list, length = restaurants.get_info(results, 0, 'Price')
    print(f"Price list for city 0: {price_list}, Length: {length}")

    print("\n--- Testing get_info_for_index(price_list, index) ---")
    index = 0
    print(f"Price at index {index}: {restaurants.get_info_for_index(price_list, index)}")

if __name__ == "__main__":
    main()
