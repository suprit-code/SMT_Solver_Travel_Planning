from tools.flights.apis import *

def main():
    print("\n--- Initializing Flights ---")
    flights = Flights()

    print("\n--- Testing load_db() ---")
    flights.load_db()
    print("Data loaded with shape:", flights.data.shape)

    flights = Flights()

    # Example test parameters
    origin = "New York"
    destination = "Los Angeles"
    departure_date = "2024-11-15"

    print("\n--- Testing run_check() ---")
    result_check = flights.run_check(origin, destination, departure_date)
    print("run_check result:", result_check)

    print("\n--- Testing run_search() ---")
    result_search = flights.run_search(origin, departure_date)
    print("run_search result:", result_search)

    print("\n--- Testing run() ---")
    result_run = flights.run(origin, destination, departure_date)
    print("run result type:", type(result_run))
    print(result_run if isinstance(result_run, str) else result_run.head())

    print("\n--- Testing run_for_annotation() ---")
    result_annot = flights.run_for_annotation(origin, destination, departure_date)
    print("run_for_annotation result:")
    print(result_annot)

    print("\n--- Testing run_for_all_cities_and_dates() ---")
    all_cities = ["New York", "Los Angeles", "Chicago"]
    cities_list = ["Los Angeles", "Chicago"]
    departure_dates = ["2024-11-15", "2024-11-16"]

    info = flights.run_for_all_cities_and_dates(origin, all_cities, cities_list, departure_dates)
    print("Z3 structure built successfully.")
    price, length = flights.get_info(info, 0, 1, 0, "Price")
    print("Sample Price array (z3 expr):", price)
    print("Sample length (z3 expr):", length)


if __name__ == "__main__":
    main()
