from z3 import *
import json
from pathlib import Path
import ast
import re
from Transit_api.apis import *
from z3_plan_scheduler import read_json_file
transits = Transits()

def parse_transportation(transport_list):
    legs = []

    for i, item in enumerate(transport_list):
        item_lower = item.lower()
        mode = None
        from_city = None
        to_city = None
        departure_time = None
        arrival_time = None
        details = {}

        if "flight number" in item_lower:
            mode = "flight"
            flight_match = re.search(r'Flight Number:\s*(.*?),', item)
            from_to_match = re.search(r'from (.*?) to (.*?),', item)
            dep_match = re.search(r'Departure Time:\s*([0-9:]+)', item)
            arr_match = re.search(r'Arrival Time:\s*([0-9:]+)', item)

            flight_number = flight_match.group(1) if flight_match else None
            from_city = from_to_match.group(1) if from_to_match else None
            to_city = from_to_match.group(2) if from_to_match else None
            departure_time = dep_match.group(1) if dep_match else None
            arrival_time = arr_match.group(1) if arr_match else None

            details = {
                "flight_number": flight_number,
                "from": from_city,
                "to": to_city,
                "departure_time": departure_time,
                "arrival_time": arrival_time
            }

        elif "self-driving" in item_lower:
            mode = "self-driving"
            from_to_match = re.search(r'from (.*?) to (.*?),', item)
            duration_match = re.search(r'duration:\s*([0-9.]+)', item)
            distance_match = re.search(r'distance:\s*([0-9.]+)', item)
            cost_match = re.search(r'cost:\s*([0-9.]+)', item)

            from_city = from_to_match.group(1) if from_to_match else None
            to_city = from_to_match.group(2) if from_to_match else None

            details = {
                "duration_minutes": float(duration_match.group(1)) if duration_match else None,
                "distance_km": float(distance_match.group(1)) if distance_match else None,
                "cost": float(cost_match.group(1)) if cost_match else None,
                "from": from_city,
                "to": to_city
            }

        elif "taxi" in item_lower:
            mode = "taxi"
            from_to_match = re.search(r'from (.*?) to (.*?)(,|$)', item)
            duration_match = re.search(r'duration:\s*([0-9.]+)', item)
            distance_match = re.search(r'distance:\s*([0-9.]+)', item)
            cost_match = re.search(r'cost:\s*([0-9.]+)', item)
            from_city = from_to_match.group(1) if from_to_match else None
            to_city = from_to_match.group(2) if from_to_match else None

            details = {
                "duration_minutes": float(duration_match.group(1)) if duration_match else None,
                "distance_km": float(distance_match.group(1)) if distance_match else None,
                "cost": float(cost_match.group(1)) if cost_match else None,
                "from": from_city,
                "to": to_city
            }

        leg = {
            "day": 2*i + 1,
            "from": from_city,
            "to": to_city,
            "mode": mode,
            "details": details
        }

        legs.append(leg)

    return {
        "legs": legs
    }

def parse_text(raw_text: str):
    lines = [line.strip() for line in raw_text.strip().split("\n") if line.strip()]
    data = {}

    for line in lines:
        key, value = line.split(":", 1)
        key = key.lower().replace(" ", "_")
        key = key.replace("(", "").replace(")", "").replace("/", "_")

        value = ast.literal_eval(value.strip().rstrip(","))
        data[key] = value

    # Extract data
    cities = data.get("destination_cities", [])
    restaurants = [r for r in data.get("restaurants_3_meals_per_day", []) if r != "-"]
    attractions = [a for a in data.get("attractions_1_per_day", []) if a != "-"]
    accommodations = data.get("accommodations_1_per_city", [])
    transportation = data.get("transportation_methods_between_cities", [])

    cities_list = []

    for i, city in enumerate(cities):
        city_attractions = [ a for a in attractions if a.split(",")[-1].strip() == city ]
        city_restaurants = [ r for r in restaurants if r.split(",")[-1].strip() == city ]
        cities_list.append({
            "city" : city,
            "accommodation": accommodations[i] if i < len(accommodations) else None,
            "restaurants": city_restaurants,
            "attractions": city_attractions
        })
    result = {}
    result["transportation"] = parse_transportation(transportation)
    result["cities"] = cities_list
    result["origin"] = result["transportation"]["legs"][0]["from"] if result["transportation"]["legs"] else None
    return result


# CONSTANTS
DAY = 24*60
travel_buffer = 30 
min_meal_gap = 4*60 + 1
self_driving_start_time = 6*60
durations = {
    "breakfast": 50,
    "lunch": 60,
    "dinner": 1*60 + 15,
    "attraction": 3*60 + 30,
    "accommodation_start_of_day": 30, # Was accommodation_start
    "accommodation_check_in": 30,     # For post-travel check-in
    "accommodation_end_of_day": 8*60,   # Was accommodation_end
    "other": 30
}
windows = {
    "breakfast": (8*60, 10*60+30), 
    "lunch": (12*60, 15*60+30), 
    "dinner": (19*60, 22*60), 
    "attraction": (9*60, 19*60), 
    "accommodation_start_of_day": (6*60, 9*60),
    "accommodation_check_in": (0*60, 24*60),    
}

def extract_cities_list(data):
    cities_list = []
    cities_list.append(data["origin"])
    cities_list.extend([x["city"] for x in data["cities"]])
    return cities_list

def extract_transportation_list(data):
    transportation_list = data.get("transportation", [])
    transport_day_index_mapping = {}
    for i, leg in enumerate(transportation_list.get("legs", [])):
        transport_day_index_mapping[leg.get("day", 1)] = i
    return transportation_list.get("legs",[]), transport_day_index_mapping

def extract_accomodation_list(data):
    accomodation_list = []
    for x in data.get("cities", []):
        acc_str = x.get("accommodation", "")
        if "," in acc_str:
            name, city = acc_str.rsplit(",", 1)
            name = name.strip()
            city = city.strip()
        else:
            name = acc_str.strip()
            city = ""
        accomodation_list.append({ "name": name, "city": city })

    return accomodation_list

def attraction_z3_mapping(data, cities):
    attractions = Array('attraction', IntSort(), IntSort())
    attractions = Store(attractions, 0, 0) # initialize for initial city
    for city in data["cities"]:
        attractions = Store(attractions, cities.index(city["city"]), len(city["attractions"]))
    return attractions

def attraction_lookup(city_index, attraction_index, data):
    cities = extract_cities_list(data)
    if city_index < 0 or city_index >= len(cities):
        return None, None
    
    city_name = cities[city_index]
    attr_list = [a for c in data["cities"] if c["city"] == city_name for a in c.get("attractions", [])]

    if attraction_index < 0 or attraction_index >= len(attr_list):
        return city_name, None
    return city_name, attr_list[attraction_index]

def restaurants_z3_mapping(data, cities):
    restaurants = Array('restaurants', IntSort(), IntSort()) 
    restaurants = Store(restaurants, 0, 0)
    for city in data["cities"]:
        restaurants = Store(restaurants, cities.index(city["city"]), len(city.get("restaurants", [])))
    return restaurants

def restaurant_lookup(city_index, restaurant_index, data):
    cities = extract_cities_list(data)
    if city_index < 0 or city_index >= len(cities):
        return None, None
    city_name = cities[city_index]
    rest_list = [r for c in data["cities"] if c["city"] == city_name for r in c.get("restaurants", [])]
    if restaurant_index < 0 or restaurant_index >= len(rest_list):
        return city_name, None
    return city_name, rest_list[restaurant_index]



def add_city_transition_constraints(opt, transportation_data, days, cities, origin):
    src_city = {}
    dest_city = {}
    
    src_city[0] = Int("src_city_0")
    opt.add(src_city[0] == cities.index(origin))

    for d in range(days):
        if d != 0:
            src_city[d] = Int(f"src_city_{d}")
        dest_city[d] = Int(f"dest_city_{d}")

    transport_days = {leg["day"] - 1 for leg in transportation_data}

    for leg in transportation_data:
        d = leg["day"] - 1
        origin_idx = cities.index(leg["details"]["from"])
        dest_idx = cities.index(leg["details"]["to"])
        opt.add(src_city[d] == origin_idx)
        opt.add(dest_city[d] == dest_idx)

    for d in range(days):
        if d not in transport_days:
            opt.add(dest_city[d] == src_city[d])
        if d < days - 1:
            opt.add(src_city[d+1] == dest_city[d])

    return src_city, dest_city


def parse_time(s):
    try:
        hh, mm = s.strip().split(":")
        return int(hh)*60 + int(mm)
    except:
        return None

def fmt_time(minutes):
    minutes = minutes % DAY
    hh = minutes // 60
    mm = minutes % 60
    return f"{hh:02d}:{mm:02d}"


def add_transportation_constraints(opt, transportation_data, intervals):
    transport_departure = {}
    transport_arrival = {}

    for leg in transportation_data:
        mode = leg["mode"]
        d = leg["day"] - 1
        day_offset = d * DAY

        dep = Int(f"transport_departure_{d}")
        arr = Int(f"transport_arrival_{d}")

        transport_departure[d] = dep
        transport_arrival[d] = arr

        opt.add(dep >= day_offset)
        opt.add(arr >= day_offset)

        if mode == "flight":
            dep_time = parse_time(leg["details"]["departure_time"])
            arr_time = parse_time(leg["details"]["arrival_time"])
            if(arr_time < dep_time):
                arr_time += DAY

            opt.add(dep == day_offset + dep_time)
            opt.add(arr == day_offset + arr_time)

        elif mode == "self-driving" or mode == "taxi":
            duration = int(leg["details"]["duration_minutes"])

            opt.add(dep >= day_offset + self_driving_start_time)
            opt.add(arr == dep + duration)
        
        intervals.append((dep, arr))

    return transport_departure, transport_arrival


def add_accommodation_constraints(opt, days, cities, accommodation_data,
                                src_city, dest_city, transport_departure,
                                transport_arrival, intervals):
    accommodation_start_index = {}
    accommodation_checkin_index = {}
    accommodation_end_day_index = {}

    acc_city_indices = [cities.index(acc["city"]) for acc in accommodation_data]
    def acc_city_expr(acc_var):
        return Sum([
            If(acc_var == i, acc_city_indices[i], 0)
            for i in range(len(acc_city_indices))
        ])

    #penalty system
    early_start_penalties = []
    short_sleep_penalties = []

    for d in range(days):
        day_offset = d * DAY
        is_travel_day = d in transport_departure

        # accommodation_start_of_day
        if(d!=0):
            accommodation_start_index[d] = Int(f"accommodation_start_index_{d}")
            opt.add(accommodation_start_index[d] >= 0)
            opt.add(accommodation_start_index[d] < len(accommodation_data))

            s_start = Int(f"s_accommodation_start_{d}")
            e_start = Int(f"e_accommodation_start_{d}")
            prev_e_end = Int(f"e_accommodation_end_{d-1}")

            preffered_start_time = day_offset + windows["accommodation_start_of_day"][0]
            early_start_penalty = Int(f"early_start_penalty_{d}")

            opt.add(early_start_penalty >= 0)
            opt.add(early_start_penalty >= preffered_start_time - s_start)
            early_start_penalties.append(early_start_penalty)
            
            opt.add(prev_e_end <= s_start)
            opt.add(e_start >= s_start + durations["accommodation_start_of_day"])
            opt.add(e_start <= day_offset + windows["accommodation_start_of_day"][1])

            if is_travel_day:
                opt.add(
                    If(s_start < transport_departure[d],
                        acc_city_expr(accommodation_start_index[d]) == src_city[d],
                        acc_city_expr(accommodation_start_index[d]) == dest_city[d])
                )
            else:
                opt.add(acc_city_expr(accommodation_start_index[d]) == src_city[d])

            intervals.append((s_start, e_start))

        if(d!=days-1):
        # accommodation_end_of_day
            accommodation_end_day_index[d] = Int(f"accommodation_end_index_{d}")
            opt.add(accommodation_end_day_index[d] >= 0)
            opt.add(accommodation_end_day_index[d] < len(accommodation_data))

            s_end = Int(f"s_accommodation_end_{d}")
            e_end = Int(f"e_accommodation_end_{d}")

            opt.add(e_end >= s_end)

            #short sleep penalty system
            actual_speep_duration = e_end - s_end
            preffered_sleep = durations["accommodation_end_of_day"]
            
            short_sleep_penalty = Int(f"short_sleep_penalty_{d}")
            opt.add(short_sleep_penalty >= 0)
            opt.add(short_sleep_penalty >= preffered_sleep - actual_speep_duration)
            short_sleep_penalties.append(short_sleep_penalty)

            # next_day_7am = day_offset + DAY + 7*60
            # opt.add(e_end == next_day_7am)
            # opt.add(s_end == e_end - durations["accommodation_end_of_day"])

            opt.add(acc_city_expr(accommodation_end_day_index[d]) == dest_city[d])

            intervals.append((s_end, e_end))

            # accommodation_check_in
            if (is_travel_day):
                accommodation_checkin_index[d] = Int(f"accommodation_checkin_index_{d}")
                opt.add(accommodation_checkin_index[d] >= 0)
                opt.add(accommodation_checkin_index[d] < len(accommodation_data))

                s_check = Int(f"s_accommodation_checkin_{d}")
                e_check = Int(f"e_accommodation_checkin_{d}")

                opt.add(e_check >= s_check + durations["accommodation_check_in"])
                opt.add(s_check == transport_arrival[d] + travel_buffer)
                opt.add(s_check >= day_offset + windows["accommodation_check_in"][0])
                opt.add(acc_city_expr(accommodation_checkin_index[d]) == dest_city[d])

                opt.add(e_check + travel_buffer <= s_end)
                intervals.append((s_check, e_check))

        if(d!=0 and d!=days-1):
            opt.add(e_start + travel_buffer <= s_end)

        #penalty optimization
        total_penalty = Sum(early_start_penalties + short_sleep_penalties)
        opt.minimize(total_penalty)

    return accommodation_start_index, accommodation_checkin_index, accommodation_end_day_index


def add_meal_constraints(opt, days, restaurants, src_city, dest_city, 
                        transport_departure, transport_arrival,
                        all_cities, intervals):

    meal_types = ["breakfast", "lunch", "dinner"]
    print("All cities:", all_cities)

    meal_taken = {}
    meal_start = {}
    meal_end = {}
    meal_city = {} 

    for d in range(days):
        for meal in meal_types:
            taken = Bool(f"{meal}_taken_{d}")
            s = Int(f"s_{meal}_{d}")
            e = Int(f"e_{meal}_{d}")
            c = Int(f"{meal}_city_{d}")

            intervals.append((s, e, taken))

            meal_taken[(d,meal)] = taken
            meal_start[(d,meal)] = s
            meal_end[(d,meal)] = e
            meal_city[(d,meal)] = c

            day_offset = d * DAY
            w_start, w_end = windows[meal]
            dur = durations[meal]

            #After Morning Accommodation 
            if d > 0:
                acc_start = Int(f"e_accommodation_start_{d}")
                opt.add(Implies(taken, s >= acc_start + travel_buffer))
            
            #Before Evening Accommodation 
            if d < days - 1:
                acc_end = Int(f"s_accommodation_end_{d}")
                opt.add(Implies(taken, e + travel_buffer <= acc_end))

            # Force meals on staying days
            if d % 2 == 1:
                opt.add(meal_taken[(d, meal)] == True)

            # ---- time window ----
            opt.add(Implies(taken,
                And(
                    s >= day_offset + w_start,
                    s <= day_offset + w_end - dur,
                    e >= s + dur
                )
            ))

            # ---------- CITY SELECTION LOGIC ----------
            if d in transport_departure:
                dep = transport_departure[d]
                arr = transport_arrival[d]

                opt.add(Implies(taken,
                    c == If(s < dep, src_city[d],
                        If(s >= arr, dest_city[d], -1))
                ))
                opt.add(Implies(taken, c != -1))
            else:
                opt.add(Implies(taken, c == src_city[d]))

            # ----------- RESTAURANTS VALIDITY CONSTRAINTS -----------
            count = Select(restaurants, c)
            opt.add(Implies(taken, And(c>=0, count > 0)))

        for m1, m2 in [("breakfast","lunch"),("lunch","dinner"),("breakfast","dinner")]:
            # ---- 4 hour gap constraint ----
            opt.add(Implies(
                And(meal_taken[(d,m1)], meal_taken[(d,m2)]),
                Or(
                    meal_start[(d,m2)] >= meal_end[(d,m1)] + min_meal_gap,
                    meal_start[(d,m1)] >= meal_end[(d,m2)] + min_meal_gap
                )
            ))
    
    for city in range(len(all_cities)):
        taken_in_city = []
        for d in range(days):
            for meal in meal_types:
                taken_in_city.append(
                    If(And(meal_taken[(d,meal)], meal_city[(d,meal)] == city), 1, 0)
                )
        opt.add(Sum(taken_in_city) <= Select(restaurants, city))

    #---Objective: Maximize number of meals taken---
    meal_score = Sum([meal_taken[(d, m)] for d in range(days) for m in meal_types])
    opt.maximize(meal_score)

    return meal_taken, meal_start, meal_end, meal_city


def add_attraction_constraints(opt, days, attractions,
                               src_city, dest_city,
                               transport_departure,
                               transport_arrival, intervals, 
                               all_cities, MAX_ATTR=1):

    attr_taken = {}
    attr_start = {}
    attr_end = {}
    attr_city = {}

    for d in range(days):
        for k in range(MAX_ATTR):
            taken = Bool(f"attr_taken_{d}_{k}")
            s = Int(f"attr_start_{d}_{k}")
            e = Int(f"attr_end_{d}_{k}")
            c = Int(f"attr_city_{d}_{k}")

            intervals.append((s, e, taken))

            attr_taken[(d,k)] = taken
            attr_start[(d,k)] = s
            attr_end[(d,k)] = e
            attr_city[(d,k)] = c

            day_offset = d * DAY

            #After Morning Accommodation (Starting Day 2)
            if d > 0:
                acc_start = Int(f"e_accommodation_start_{d}")
                opt.add(Implies(taken, s >= acc_start + travel_buffer))
            
            #Before Evening Accommodation (Ending before the last day)
            if d < days - 1:
                acc_end = Int(f"s_accommodation_end_{d}")
                opt.add(Implies(taken, e + travel_buffer <= acc_end))

            # ---- time inside day ----
            w_start, w_end = windows["attraction"]
            dur = durations["attraction"]

            opt.add(Implies(taken,
                And(
                    s >= day_offset + w_start,
                    s <= day_offset + w_end - dur,
                    e >= s + dur
                )
            ))

            # ---- city selection logic  ----
            if d in transport_departure:
                dep = transport_departure[d]
                arr = transport_arrival[d]

                opt.add(Implies(taken,
                    c == If(s < dep, src_city[d],
                    If(s >= arr, dest_city[d], -1))
                ))
                opt.add(Implies(taken, c != -1))
            else:
                opt.add(Implies(taken, c == src_city[d]))

            # ---- attraction validity ----
            count = Select(attractions, c)
            opt.add(Implies(taken, And(c >= 0, count > 0)))
    
    for city in range(len(all_cities)):
        taken_in_city = []
        for d in range(days):
            for k in range(MAX_ATTR):
                taken_in_city.append(
                    If(And(attr_taken[(d,k)], attr_city[(d,k)] == city), 1, 0)
                )

        opt.add(Sum(taken_in_city) <= Select(attractions, city))

    # ---- Objective: maximize attractions ----
    attr_score = Sum([
        If(attr_taken[(d,k)], 1, 0)
        for d in range(days)
        for k in range(MAX_ATTR)
    ])

    opt.maximize(attr_score)

    return attr_taken, attr_start, attr_end, attr_city


def add_global_no_overlap(opt, intervals):
    """
    Automatically finds all (s_x, e_x) interval pairs in solver
    and adds non-overlapping constraints between them.
    """
    for i in range(len(intervals)):
        for j in range(i+1, len(intervals)):
            a = intervals[i]
            b = intervals[j]
            if len(a) == 2:
                s1,e1 = a
                cond1 = True
            else:
                s1,e1,cond1 = a
            if len(b) == 2:
                s2,e2 = b
                cond2 = True
            else:
                s2,e2,cond2 = b

            opt.add(Implies(
                And(cond1, cond2),
                Or(e1 + travel_buffer <= s2, e2 + travel_buffer <= s1)
            ))


def get_transit_info(transits_api, city, poi_name):
    if not city or not poi_name:
        return ""
    try:
        result = transits_api.run(city, poi_name)
        if result is not None and not result.empty:
            return f"nearest transit : {result.iloc[0]['nearest_stop_name']}, {result.iloc[0]['nearest_stop_distance']}m away"
    except Exception as e:
        print(f"Warning: Transit API failed for {poi_name} in {city}: {e}")
    return ""


def scheduler(data, days, origin):
    transits = Transits()
    opt = Optimize()
    MAX_ATTR = 1
    intervals = []

    cities = extract_cities_list(data)
    transportation_data, transport_day_index_mapping = extract_transportation_list(data)
    accommodation_data = extract_accomodation_list(data)

    # City transitions
    src_city, dest_city = \
        add_city_transition_constraints(opt, transportation_data, days, cities, origin)

    # Transportation
    transport_departure, transport_arrival = \
        add_transportation_constraints(opt, transportation_data, intervals)

    # Accommodation
    start_idx, checkin_idx, end_idx = \
        add_accommodation_constraints(
            opt, days, cities, accommodation_data, src_city, dest_city,
            transport_departure, transport_arrival, intervals
        )
    
    # Restaurants
    restaurants = restaurants_z3_mapping(data, cities)
    meal_taken, meal_start, meal_end, meal_city = \
        add_meal_constraints(
            opt, days, restaurants, src_city, dest_city,
            transport_departure, transport_arrival, cities,
            intervals
        )
    
    # Attractions
    attractions = attraction_z3_mapping(data, cities)
    attr_taken, attr_start, attr_end, attr_city = \
        add_attraction_constraints(
            opt, days, attractions, src_city, dest_city,
            transport_departure, transport_arrival, intervals, 
            cities, MAX_ATTR
        )
    
    # Global no-overlap
    add_global_no_overlap(opt, intervals)

    result = opt.check()
    print("Solver result:", result)

    if result != sat:
        print("Model UNSAT ❌")
        print(opt.unsat_core())
        return {}

    model = opt.model()

    plan = {"days": []}

    used_attraction = {i: 0 for i in range(len(cities))}
    used_meals = {i : 0 for i in range(len(cities))}

    for d in range(days):
        day_dict = {
            "day": d + 1,
            "current_city": "-",
            "transportation": "-",
            "breakfast": "-",
            "lunch": "-",
            "dinner": "-",
            "attraction": "-",
            "accommodation": "-",
            "event": "-",
            "point_of_interest_list": "-"
        }

        poi_entries = []

        # Transportation
        if d in transport_departure:
            dep = model[transport_departure[d]].as_long()
            arr = model[transport_arrival[d]].as_long()

            leg_idx = transport_day_index_mapping[d+1]
            leg = transportation_data[leg_idx]

            mode = leg["mode"]
            from_city = leg["details"]["from"]
            to_city = leg["details"]["to"]
            dur = leg["details"].get("duration_minutes", "N/A")
            dist = leg["details"].get("distance_km", "N/A")
            tcost = leg["details"].get("cost", "N/A")


            if mode == "flight":
                flight_no = leg["details"]["flight_number"]
                day_dict["transportation"] = (
                    f"Flight Number: {flight_no}, "
                    f"from {from_city} to {to_city}, "
                    f"Departure Time: {fmt_time(dep)}, "
                    f"Arrival Time: {fmt_time(arr)}"
                )
            else:
                day_dict["transportation"] = (
                    f"{mode.capitalize()} from {from_city} to {to_city}, "
                    f"duration: {dur}, "
                    f"distance: {dist}, "
                    f"cost : {tcost}"
                )
            day_dict["current_city"] = f"from {from_city} to {to_city}"


        # Accommodation
        acc_name = "-"
        # START
        if d in start_idx:
            s_start = model[Int(f"s_accommodation_start_{d}")].as_long()
            e_start = model[Int(f"e_accommodation_start_{d}")].as_long()
            acc_idx = model[start_idx[d]].as_long()
            accomodation = accommodation_data[acc_idx]["name"]
            accomodation_city = accommodation_data[acc_idx]["city"]
            transit = get_transit_info(transits, accomodation_city, accomodation)
            poi_entries.append((s_start, f"{accomodation}, stay from {fmt_time(s_start)} to {fmt_time(e_start)}, {transit}"))

        # CHECKIN
        if d in checkin_idx:
            s_check = model[Int(f"s_accommodation_checkin_{d}")].as_long()
            e_check = model[Int(f"e_accommodation_checkin_{d}")].as_long()
            acc_idx = model[checkin_idx[d]].as_long()
            accomodation = accommodation_data[acc_idx]["name"]
            accomodation_city = accommodation_data[acc_idx]["city"]
            transit = get_transit_info(transits, accomodation_city, accomodation)
            poi_entries.append((s_check, f"{accomodation}, stay from {fmt_time(s_check)} to {fmt_time(e_check)}, {transit}"))

        # END
        if d in end_idx:
            s_end = model[Int(f"s_accommodation_end_{d}")].as_long()
            e_end = model[Int(f"e_accommodation_end_{d}")].as_long()
            acc_idx = model[end_idx[d]].as_long()
            acc_name = accommodation_data[acc_idx]["name"]
            city_name = accommodation_data[acc_idx]["city"]
            transit = get_transit_info(transits, city_name, acc_name)
            poi_entries.append((s_end, f"{acc_name}, stay from {fmt_time(s_end)} to {fmt_time(e_end)}, {transit}"))
            day_dict["accommodation"] = f"{acc_name}, {city_name}"

        # set city name and event name properly
        if day_dict["current_city"] == "-":
            # Try to infer from accommodation
            if day_dict["accommodation"] != "-":
                city_name = day_dict["accommodation"].split(",")[-1].strip()
                day_dict["current_city"] = city_name
                #events code

        # Meals
        for meal in ["breakfast", "lunch", "dinner"]:
            if is_true(model[meal_taken[(d, meal)]]):
                city_idx = model[meal_city[(d, meal)]].as_long()
                rest_idx = used_meals[city_idx]
                used_meals[city_idx] += 1
                city_name, rest_name = restaurant_lookup(city_idx, rest_idx, data)
                transit = get_transit_info(transits, city_name, rest_name)

                day_dict[meal] = f"{rest_name}"

                s = model[meal_start[(d, meal)]].as_long()
                e = model[meal_end[(d, meal)]].as_long()

                poi_entries.append((s, f"{rest_name}, visit from {fmt_time(s)} to {fmt_time(e)}, {transit}"))

        # Attractions
        attraction_list = []

        for k in range(MAX_ATTR):
            if is_true(model[attr_taken[(d, k)]]):
                city_idx = model[attr_city[(d, k)]].as_long()
                attr_idx = used_attraction[city_idx]
                used_attraction[city_idx] += 1
                city_name, attr_name = attraction_lookup(city_idx, attr_idx, data)
                transit = get_transit_info(transits, city_name, attr_name)

                attraction_list.append(f"{attr_name}")

                s = model[attr_start[(d, k)]].as_long()
                e = model[attr_end[(d, k)]].as_long()

                poi_entries.append((s, f"{attr_name}, visit from {fmt_time(s)} to {fmt_time(e)}, {transit}"))

        if attraction_list:
            day_dict["attraction"] = "; ".join(attraction_list)


        # POI list
        if poi_entries:
            poi_entries.sort(key=lambda x: x[0])
            poi_entries = [entry[1] for entry in poi_entries] 
            day_dict["point_of_interest_list"] = "; ".join(poi_entries)

        plan["days"].append(day_dict)

    return plan


if __name__ == "__main__":
    BASE_PATH = Path("Tripcraft_outputv4") / "7d" / "phi_nl" 
    days = 7

    unsat_indexes = []
    error_indexes = []

    if days == '3':
        index = 344
    elif days == '5':
        index = 324
    elif days == '7':
        index = 332
    else:
        index = 344

    for index in range(index):
        i = index + 1
        try:
            path = BASE_PATH / str(i) / "plans" / "plan.txt"
            write_path = BASE_PATH / str(i) / "plans" / "plan_with_poi.txt"

            if not path.exists():
                print(f"[{i}] ❌ Missing file")
                error_indexes.append(i)
                continue

            print(f"Checking plan {i}...")

            with open(path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            data = parse_text(raw_text)
            origin = data["origin"]

            plan = scheduler(data, days, origin)

            if plan == {}:
                unsat_indexes.append(i)

            with open(write_path, 'w', encoding='utf-8') as f:
                json.dump(plan["days"], f, indent=2 , ensure_ascii=False)

        except Exception as e:
            print(f"[{i}] 💥 ERROR: {e}")
            error_indexes.append(i)

    print("\n==============================")
    print("UNSAT INDEXES:")
    print(unsat_indexes)
    print("\nERROR INDEXES:")
    print(error_indexes)
    print("==============================")