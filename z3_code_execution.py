import os, sys
import time
import json
import traceback

import pandas as pd
from tqdm import tqdm
from z3 import *
from open_source_models import *
from typing import List, Dict, Any

from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "tools/planner")))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "../tools/planner")))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from tools.cities.apis import *
from tools.flights.apis import *
from tools.accommodations.apis import *
from tools.attractions.apisv3 import *
from tools.googleDistanceMatrix.apis import *
from tools.restaurants.apis import *

CitySearch = Cities()
FlightSearch = Flights()
AttractionSearch = Attractions()
DistanceSearch = GoogleDistanceMatrix()
AccommodationSearch = Accommodations()
RestaurantSearch = Restaurants()



def convert_to_int(real):
    out = ToInt(real) # ToInt(real + 0.0001)
    out += If(real == out, 0, 1)
    return out

def get_arrivals_list(transportation_arrtime, day, variables):
    arrives = []
    if day == 3: 
        arrives.append(transportation_arrtime[0])
        arrives.append(IntVal(-1))
        arrives.append(transportation_arrtime[1])
    elif day == 5:
        arrives.append(transportation_arrtime[0])
        arrives.append(If(variables[1] == 1, transportation_arrtime[1], IntVal(-1)))
        arrives.append(If(variables[1] == 2, transportation_arrtime[1], IntVal(-1)))
        arrives.append(If(variables[1] == 3, transportation_arrtime[1], IntVal(-1)))
        arrives.append(transportation_arrtime[2])
    else:
        arrives.append(transportation_arrtime[0])
        arrives.append(If(variables[1] == 1, transportation_arrtime[1], If(variables[2] == 1, transportation_arrtime[2], IntVal(-1))))
        arrives.append(If(variables[1] == 2, transportation_arrtime[1], If(variables[2] == 2, transportation_arrtime[2], IntVal(-1))))
        arrives.append(If(variables[1] == 3, transportation_arrtime[1], If(variables[2] == 3, transportation_arrtime[2], IntVal(-1))))
        arrives.append(If(variables[1] == 4, transportation_arrtime[1], If(variables[2] == 4, transportation_arrtime[2], IntVal(-1))))
        arrives.append(If(variables[1] == 5, transportation_arrtime[1], If(variables[2] == 5, transportation_arrtime[2], IntVal(-1))))
        arrives.append(transportation_arrtime[3])
    return arrives

def get_city_list(city, day, departure_dates):
    city_list = []
    if day == 3: 
        city_list.append(IntVal(-1))
        city_list.append(IntVal(0))
        city_list.append(IntVal(0))
        city_list.append(IntVal(-1))
    elif day == 5:
        city_list.append(IntVal(-1))
        city_list.append(city[0])
        city_list.append(If(departure_dates[1] <= 1, city[1],city[0]))
        city_list.append(If(departure_dates[1] <= 2, city[1], city[0]))
        city_list.append(If(departure_dates[1] <= 3, city[1], city[0]))
        city_list.append(IntVal(-1))
    else:
        city_list.append(IntVal(-1))
        city_list.append(city[0])
        city_list.append(If(departure_dates[2] <= 1, city[2],If(departure_dates[1] <= 1, city[1],city[0])))
        city_list.append(If(departure_dates[2] <= 2, city[2], If(departure_dates[1] <= 2, city[1],city[0])))
        city_list.append(If(departure_dates[2] <= 3, city[2], If(departure_dates[1] <= 3, city[1],city[0])))
        city_list.append(If(departure_dates[2] <= 4, city[2], If(departure_dates[1] <= 4, city[1],city[0])))
        city_list.append(If(departure_dates[2] <= 5, city[2], If(departure_dates[1] <= 5, city[1],city[0])))
        city_list.append(IntVal(-1))
    return city_list

def generate_as_plan(s, variables, query):
    CitySearch = Cities()
    FlightSearch = Flights()
    AttractionSearch = Attractions()
    DistanceSearch = GoogleDistanceMatrix()
    AccommodationSearch = Accommodations()
    RestaurantSearch = Restaurants()
    cities = []
    transportation = []
    departure_dates = []
    transportation_info = []
    restaurant_city_list = []
    attraction_city_list = []
    accommodation_city_list = []
    if query['visiting_city_number'] == 1:
        cities = [query['dest']]
        cities_list = [query['dest']]
    else:
        cities_list = CitySearch.run(query['dest'], query['org'], query['date'])
        if query['org'] in cities_list:
            cities_list.remove(query['org'])
        for city in variables['city']:
            cities.append(cities_list[int(s.model()[city].as_long())])
    for i, flight in enumerate(variables['flight']):
        if bool(s.model()[flight]):
            transportation.append('flight')
        elif bool(s.model()[variables['self-driving'][i]]):
            transportation.append('self-driving')
        else:
            transportation.append('taxi')
    for date_index in variables['departure_dates']:
        departure_dates.append(query['date'][int(s.model()[date_index].as_long())])
    dest_cities = [query['org']] + cities + [query['org']]
    for i, index in enumerate(variables['flight_index']):
        if transportation[i] == 'flight':
            flight_index = int(s.model()[index].as_long())
            flight_list = FlightSearch.run(dest_cities[i], dest_cities[i+1], departure_dates[i])
            # flight_info = f'Flight Number: {np.array(flight_list['Flight Number'])[flight_index]}, from {np.array(flight_list['OriginCityName'])[flight_index]} to {np.array(flight_list['DestCityName'])[flight_index]}, Departure Time: {np.array(flight_list['DepTime'])[flight_index]}, Arrival Time: {np.array(flight_list['ArrTime'])[flight_index]}'
            flight_info = 'Flight Number: {}, from {} to {}, Departure Time: {}, Arrival Time: {}'.format(np.array(flight_list['Flight Number'])[flight_index], np.array(flight_list['OriginCityName'])[flight_index], np.array(flight_list['DestCityName'])[flight_index], np.array(flight_list['DepTime'])[flight_index], np.array(flight_list['ArrTime'])[flight_index])
            transportation_info.append(flight_info)
        elif transportation[i] == 'self-driving':
            transportation_info.append('Self-' + DistanceSearch.run(dest_cities[i], dest_cities[i+1], mode='driving'))
        else:
            # pdb.set_trace()
            transportation_info.append(DistanceSearch.run(dest_cities[i], dest_cities[i+1], mode='taxi'))
    for i,which_city in enumerate(variables['restaurant_in_which_city']):
        # pdb.set_trace()
        city_index = int(s.model()[which_city].as_long())
        if city_index == -1:
            restaurant_city_list.append('-')
        else:
            city = cities_list[city_index]
            restaurant_list = RestaurantSearch.run(city)
            restaurant_index = int(s.model()[variables['restaurant_index'][i]].as_long())
            restaurant = np.array(restaurant_list['Name'])[restaurant_index]
            restaurant_city_list.append(restaurant + ', ' + city)

    for i,which_city in enumerate(variables['attraction_in_which_city']):
        city_index = int(s.model()[which_city].as_long())
        if city_index == -1:
            attraction_city_list.append('-')
        else:
            city = cities_list[city_index]
            attraction_list = AttractionSearch.run(city)
            attraction_index = int(s.model()[variables['attraction_index'][i]].as_long())
            print("Attraction index:", attraction_index)
            attraction = np.array(attraction_list['Name'])[attraction_index]
            attraction_city_list.append(attraction + ', ' + city)

    for i,city in enumerate(cities):
        accommodation_list = AccommodationSearch.run(city)
        accommodation_index = int(s.model()[variables['accommodation_index'][i]].as_long())
        accommodation = np.array(accommodation_list['NAME'])[accommodation_index]
        accommodation_city_list.append(accommodation + ', ' + city)
    print(cities)
    print(transportation)
    print(departure_dates)
    print(transportation_info)
    print(restaurant_city_list)
    print(attraction_city_list)
    print(accommodation_city_list)
    return f'Destination cities: {cities},\nTransportation dates: {departure_dates},\nTransportation methods between cities: {transportation_info},\nRestaurants (3 meals per day): {restaurant_city_list},\nAttractions (1 per day): {attraction_city_list},\nAccommodations (1 per city): {accommodation_city_list}'


def run_single_job(job_id, code, query_json, user_persona, path):
    try:
        start_time = time.time()

        # Start with a copy of current globals
        exec_env = globals().copy()

        # Inject runtime variables
        exec_env.update({
            "__name__": "__main__",
            "query_json": query_json,
            "user_persona": user_persona,
            "variables": {},
            "path": path,
            "success": False
        })

        exec(code, exec_env)

        return {
            "job_id": job_id,
            "status": "success",
            "time": time.time() - start_time
        }

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()

        error_file = os.path.join(path, "error.txt")  
        os.makedirs(path, exist_ok=True)
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(f"\n--- JOB {job_id} FAILED ---\n")
            f.write(f"Error: {error_msg}\n")
            f.write(f"Traceback:\n{tb}\n")
            f.write(f"{'-'*40}\n")

        return {
            "job_id": job_id,
            "status": "failed",
            "error": error_msg,
            "traceback": tb
        }

def main():
    start_time = time.time()
    MAX_WORKERS = mp.cpu_count()
    print("Max workers:", MAX_WORKERS)

    query_data_list = pd.read_csv("tripcraft_3day.csv")     #change
    path = "output2/3d/qwen_nl"                       #change
    results = []


    with ProcessPoolExecutor(max_workers=int(MAX_WORKERS/2)) as executor:          #change
        futures = []

        for i in range(344):                                                 #change
            number = i + 1
            if os.path.exists(path + f'/{number}/plans/plan.txt'):
                print(f"[SKIP] plan.txt already generated for job {number}")
                continue

            print(f"================= Trial {number} =================")
            updated_path = path + f'/{number}/'
            try:
                with open(path + f'/{number}/plans/query.json', 'r') as f:
                    query_json = json.load(f)

                with open(path + f'/{number}/codes/codes.txt', 'r') as f:
                    code = f.read()

            except FileNotFoundError as e:
                print(f"[SKIP] Missing file for job {number}: {e}")
                continue

            user_persona = query_data_list['persona'][number - 1]

            futures.append(
                executor.submit(
                    run_single_job,
                    number,
                    code,
                    query_json,
                    user_persona,
                    updated_path
                )
            )

        output_file = os.path.join("output", "run_results3d.jsonl")              #change
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        # write each result as a JSON line so we can inspect partial runs
        with open(output_file, "a", encoding="utf-8") as out_f:
            for future in tqdm(as_completed(futures), total=len(futures)):
                result = future.result()
                results.append(result)
                out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                print(f"Written result for job {result.get('job_id')} (status={result.get('status')})")

        # also write a full JSON summary
        summary_file = os.path.join("output", "run_results3d.json")              #change
        with open(summary_file, "w", encoding="utf-8") as sf:
            json.dump(results, sf, indent=2, ensure_ascii=False)
        print(f"All results written to {output_file} and summary to {summary_file}")
        end_time = time.time()
        print("Total time taken: ", end_time - start_time)


if __name__ == "__main__":
    mp.freeze_support()
    main()