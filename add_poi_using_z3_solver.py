from z3 import Int, Optimize, Or, Abs, Sum
import re
import random
import os
import ast
import json
from tools.transits.apis import *

# --- Helper Functions ---

def fmt(m):
    DAY = 24*60
    if m >= DAY:
        m2 = m - DAY
        h = m2 // 60
        mm = m2 % 60
        return f"{h:02d}:{mm:02d}"
    else:
        h = m // 60
        mm = m % 60
        return f"{h:02d}:{mm:02d}"

def parse_time_hhmm(s):
    try:
        hh, mm = s.strip().split(":")
        return int(hh)*60 + int(mm)
    except:
        return None

# --- Helper functions for parsing itinerary ---

def parse_city_route(current_city_str):
    """Parses 'from A to B' or just 'B'"""
    if "from" in current_city_str:
        parts = current_city_str.replace("from", "").split(" to ")
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip(), True # origin, dest, is_travel
    return current_city_str.strip(), current_city_str.strip(), False # origin, dest, is_travel

def parse_poi_name_city(poi_str):
    """Parses 'POI Name, City Name'"""
    parts = poi_str.split(',')
    if len(parts) > 1:
        city = parts[-1].strip()
        name = ",".join(parts[:-1]).strip()
        return name, city
    return poi_str.strip(), None # No city found

# def parse_travel_duration(transport_str):
#     """Parses travel duration from the transportation string"""
#     if not transport_str or transport_str == "-":
#         return 0
#     match = re.search(r"Duration: ([\d\.]+)", transport_str)
#     if match:
#         try:
#             return float(match.group(1))
#         except:
#             return 0
#     return 0

def parse_transportation(transport_str):
    """
    Parses transportation string for 'driving' (duration) or 'flight' (fixed times).
    """
    if not transport_str or transport_str == "-":
        return None

    flight_match = re.search(r"Departure Time: ([\d:]+), Arrival Time: ([\d:]+)", transport_str)
    if flight_match:
        dep_time_str = flight_match.group(1)
        arr_time_str = flight_match.group(2)
        
        dep_min = parse_time_hhmm(dep_time_str)
        arr_min = parse_time_hhmm(arr_time_str)
        
        if dep_min is not None and arr_min is not None:
            if arr_min < dep_min:
                arr_min += 24*60   # Handle overnight flights (e.g., 22:00 to 02:00)
            return {'type': 'flight', 'departure': dep_min, 'arrival': arr_min}

    # driving duration
    driving_match = re.search(r"duration: ([\d\.]+)", transport_str, re.IGNORECASE)
    if driving_match:
        try:
            duration = float(driving_match.group(1))
            return {'type': 'driving', 'duration': duration}
        except:
            return None 
    return None 

def get_transit_info(transits_api, city, poi_name):
    """
    Safely calls the transit API and returns transit info or 'N/A'.
    """
    if not city or not poi_name:
        return "N/A", "N/A"
    try:
        result = transits_api.run(city, poi_name)
        if result is not None and not result.empty:
            return result.iloc[0]["nearest_stop_name"], result.iloc[0]["nearest_stop_distance"]
    except Exception as e:
        print(f"Warning: Transit API failed for {poi_name} in {city}: {e}")
    return "N/A", "N/A"

# --- Policy / Parameters  ---
travel_buffer = 25
min_meal_gap = 4*60
min_sleep = 5*60
durations = {
    "breakfast": 40,
    "lunch": 40,
    "dinner": 40,
    "attraction": 2*60,
    "accommodation_start_of_day": 30, # Was accommodation_start
    "accommodation_check_in": 20,     # For post-travel check-in
    "accommodation_end_of_day": 9*60,   # Was accommodation_end
    "travel": 0, 
    "other": 30
}
windows = {
    "breakfast": (8*60, 10*60+30), 
    "lunch": (12*60, 15*60+30), 
    "dinner": (19*60, 22*60), 
    "attraction": (9*60, 19*60), 
    "accommodation_start_of_day": (8*60, 10*60),
    "accommodation_check_in": (8*60, 24*60 + 3*60),    
}

# --- Main Scheduling Function ---

def schedule_day(transits_api, day_data, last_day_accom_name):
    """
    Generates a timed itinerary for a single day, handling inter-city travel.
    """
    origin_city, dest_city, is_travel_day = parse_city_route(day_data['current_city'])
    travel_info = parse_transportation(day_data.get('transportation'))
    
    # print(f"--- Scheduling Day {day_data.get('days') or day_data.get('day')} ({day_data['current_city']}) ---")
    # if last_day_accom_name:
    #     print(f"Starting from: {last_day_accom_name}")
        
    # --- Build POI list from day_data ---
    raw_pois = []
    for poi_type in ['breakfast', 'lunch', 'dinner', 'attraction']:
        poi_str = day_data.get(poi_type, "-")
        if not poi_str or poi_str == "-": continue

        if poi_type == 'attraction':
            pieces = [p.strip() for p in poi_str.split(';') if p.strip()]
            for p in pieces:
                name, city = parse_poi_name_city(p)
                transit_name, transit_dist = get_transit_info(transits_api, city or dest_city, name)
                raw_pois.append({'name': name, 'type': 'attraction', 'city': city or dest_city, 'transit_name': transit_name, 'transit_dist': transit_dist})
        else:
            name, city = parse_poi_name_city(poi_str)
            transit_name, transit_dist = get_transit_info(transits_api, city or dest_city, name)
            raw_pois.append({'name': name, 'type': poi_type, 'city': city or dest_city, 'transit_name': transit_name, 'transit_dist': transit_dist})

    # Find CURRENT day's accommodation
    accom_name_raw = day_data.get('accommodation')
    has_accommodation = accom_name_raw and accom_name_raw != "-"
    if has_accommodation:
        current_day_accom_name, current_day_accom_city = parse_poi_name_city(accom_name_raw)
    else:
        current_day_accom_name = None
        current_day_accom_city = None
        # print("Note: No accommodation provided for this day.")

    # --- Final ordered POIs for Z3 ---
    po_is = []
    
    # Add START of day event (from last night's accommodation)
    if last_day_accom_name:
        start_transit_name, start_transit_dist = get_transit_info(transits_api, origin_city, last_day_accom_name)
        po_is.append({'name': last_day_accom_name, 'type': 'accommodation_start_of_day', 'city': origin_city, 'transit_name': start_transit_name, 'transit_dist': start_transit_dist})

    # Add all parsed meals/attractions
    po_is.extend(raw_pois)
    
    # Add travel event
    travel_idx = -1
    if is_travel_day and travel_info:
        po_is.append({
            'name': f"Travel {origin_city} to {dest_city}",
            'type': 'travel',
            'city': 'N/A',
            'travel_details': travel_info
        })
        travel_idx = len(po_is) - 1

    # Add CHECK-IN and END of day events (for current day's accommodation)
    if has_accommodation:
        transit_name, transit_dist = get_transit_info(transits_api, current_day_accom_city or dest_city, current_day_accom_name)
        if is_travel_day:
            po_is.append({'name': current_day_accom_name, 'type': 'accommodation_check_in', 'city': current_day_accom_city or dest_city, 'transit_name': transit_name, 'transit_dist': transit_dist})
        po_is.append({'name': current_day_accom_name, 'type': 'accommodation_end_of_day', 'city': current_day_accom_city or dest_city, 'transit_name': transit_name, 'transit_dist': transit_dist})

    # --- Z3 Model ---
    opt = Optimize()
    all_penalties = []
    s_vars = {}
    e_vars = {}
    NEXT_DAY_08 = 24*60 + 8*60

    for i, p in enumerate(po_is):
        s = Int(f"s_{i}")
        e = Int(f"e_{i}")
        s_vars[i] = s
        e_vars[i] = e
        typ = p['type']

        if typ == 'travel':
            details = p['travel_details']
            if details['type'] == 'flight':
                # FLIGHT: Times are fixed.
                dep_min = details['departure']
                arr_min = details['arrival']
                opt.add(s == dep_min)
                opt.add(e == arr_min)
            elif details['type'] == 'driving':
                # DRIVING: Duration is fixed, start time is flexible.
                dur = int(details['duration'])
                opt.add(e == s + dur)
            

        if typ == 'accommodation_end_of_day':
            opt.add(e == NEXT_DAY_08) 
            
            min_sleep = 5 * 60              # Ensure you stay at least some minimum time (e.g., 5 hours) to keep it realistic
            opt.add(s <= e - min_sleep)

            dur = durations.get(typ, durations['other'])
            ideal_sleep_start = NEXT_DAY_08 - dur
            p_sleep = Int(f"p_sleep_{i}")
            opt.add(p_sleep >= 0)
            opt.add(p_sleep >= s - ideal_sleep_start)   # Penalty if you go to bed later than the ideal 23:00
            all_penalties.append(p_sleep)

            opt.add(s >= 0, e > s, e <= NEXT_DAY_08)
        elif typ == 'travel':
            details = p['travel_details']
            if details['type'] == 'driving':
                opt.add(s >= 8*60, s < NEXT_DAY_08)
                opt.add(e > s) 
            elif details['type'] == 'flight':
                pass           
        else:
            opt.add(s >= 0, s < NEXT_DAY_08)
            opt.add(e > s, e <= NEXT_DAY_08)

            dur = durations.get(typ, durations['other'])
            min_allowable_dur = int (dur / 3)
            opt.add(e >= s + min_allowable_dur)

            #Penalty for shortening the activity
            p_dur = Int(f"p_dur_{i}")
            opt.add(p_dur >= 0)
            # Penalty = Ideal Duration - Actual Duration
            opt.add(p_dur >= dur - (e - s))
            all_penalties.append(p_dur)

            if typ in ['breakfast', 'lunch', 'dinner']:
                # --- Soft constraints for meals ---
                if typ in windows:
                    w_lo, w_hi = windows[typ]
                    latest_start = w_hi - dur

                    # Penalty for starting too early
                    p_lo = Int(f"p_lo_{i}")
                    opt.add(p_lo >= 0)
                    opt.add(p_lo >= w_lo - s) 
                    all_penalties.append(p_lo)

                    # Penalty for starting too late
                    p_hi = Int(f"p_hi_{i}")
                    opt.add(p_hi >= 0)
                    opt.add(p_hi >= s - latest_start) 
                    all_penalties.append(p_hi)
            elif typ in windows:
                w_lo, w_hi = windows[typ]
                opt.add(s >= w_lo, s <= w_hi - dur)

    # --- Constraints ---
    n = len(po_is)

    # No overlaps 
    for i in range(n):
        for j in range(i+1, n):
            opt.add(Or(e_vars[i] + travel_buffer <= s_vars[j], e_vars[j] + travel_buffer <= s_vars[i]))
            
    # Meal gaps
    lunch_idxs = [i for i,p in enumerate(po_is) if p['type']=='lunch']
    dinner_idxs = [i for i,p in enumerate(po_is) if p['type']=='dinner']
    breakfast_idxs = [i for i,p in enumerate(po_is) if p['type']=='breakfast']
    for bi in breakfast_idxs:
        for li in lunch_idxs:
            # opt.add(s_vars[li] >= e_vars[bi] + min_meal_gap)
            p_gap = Int(f"p_gap_b{bi}_l{li}")
            opt.add(p_gap >= 0)
            opt.add(p_gap >= (e_vars[bi] + min_meal_gap) - s_vars[li])
            all_penalties.append(p_gap)
    for li in lunch_idxs:
        for di in dinner_idxs:
            # opt.add(s_vars[di] >= e_vars[li] + min_meal_gap)
            p_gap = Int(f"p_gap_l{li}_d{di}")
            opt.add(p_gap >= 0)
            opt.add(p_gap >= (e_vars[li] + min_meal_gap) - s_vars[di])
            all_penalties.append(p_gap)

    # ---  Accommodation and Travel Constraints ---
    
    # Find indices of our special events
    start_of_day_idx = -1
    check_in_idx = -1
    end_of_day_idx = -1
    
    for i, p in enumerate(po_is):
        if p['type'] == 'accommodation_start_of_day':
            start_of_day_idx = i
        elif p['type'] == 'accommodation_check_in':
            check_in_idx = i
        elif p['type'] == 'accommodation_end_of_day':
            end_of_day_idx = i

    # End of day is after all other events (except itself)
    if end_of_day_idx != -1:
        for i,p in enumerate(po_is):
            if i != end_of_day_idx:
                opt.add(e_vars[end_of_day_idx] >= e_vars[i])

    if start_of_day_idx != -1:
        for i, p in enumerate(po_is):
            if i not in [start_of_day_idx, check_in_idx, end_of_day_idx, travel_idx]:
                # Force all other activities to be *after* leaving the hotel
                opt.add(s_vars[i] >= e_vars[start_of_day_idx] + travel_buffer)

    # Travel-Aware Constraints
    if is_travel_day and travel_idx != -1:
        s_travel = s_vars[travel_idx]
        e_travel = e_vars[travel_idx]

        destination_anchor = e_travel
        
        # Check-in must be AFTER travel
        if check_in_idx != -1:
            opt.add(s_vars[check_in_idx] >= e_travel + travel_buffer)
            destination_anchor = e_vars[check_in_idx]
        
        # Anchor all other POIs relative to travel
        for i, p in enumerate(po_is):
            # Skip all special events
            if i in [travel_idx, start_of_day_idx, check_in_idx, end_of_day_idx]:
                continue
            
            if p['city'] == origin_city:
                opt.add(e_vars[i] + travel_buffer <= s_travel)      #This activity must finish before the travel event begins.
            elif p['city'] == dest_city:
                opt.add(s_vars[i] >= destination_anchor + travel_buffer)    #his activity must start after you have arrived and finished checking into your hotel
                
    elif has_accommodation:
        if end_of_day_idx != -1:
            for i,p in enumerate(po_is):
                if i not in [start_of_day_idx, end_of_day_idx]:
                    # Activities must finish BEFORE returning to the hotel
                    opt.add(e_vars[i] + travel_buffer <= s_vars[end_of_day_idx])

    # --- Objective  ---
    # max_end = Int("max_end")
    # opt.add(max_end >= 0)
    # for i in range(n):
    #     weight = random.randint(0, 30)
    #     opt.minimize(e_vars[i] + weight)
    # opt.minimize(max_end)

    lateness_cost = Int("lateness_cost")
    lateness_terms = []
    for i, p in enumerate(po_is):
        if p['type'] != 'accommodation_end_of_day':
            lateness_terms.append(e_vars[i])
    
    if lateness_terms:
        opt.add(lateness_cost == Sum(lateness_terms))
    else:
        opt.add(lateness_cost == 0)

    total_penalty = Int("total_penalty")
    if all_penalties:
        opt.add(total_penalty == Sum(all_penalties))
    else:
        opt.add(total_penalty == 0)
    PENALTY_WEIGHT = 1000 
    opt.minimize((total_penalty * PENALTY_WEIGHT) + lateness_cost)

    # --- Solve and Print ---
    res = opt.check()
    # print("Solver result:", res)
    poi_list_str = "No feasible schedule found."

    if res.r != 1:
        print("No feasible schedule found.")
    else:
        m = opt.model()

        final_penalty_val = m[total_penalty].as_long()
        # if final_penalty_val > 0:
            # print(f"WARNING: Schedule found with violations. Total Penalty Score: {final_penalty_val}")

        schedule = []
        for i,p in enumerate(po_is):
            s = m[s_vars[i]].as_long()
            e = m[e_vars[i]].as_long()
            schedule.append({
                's': s, 'e': e, 'name': p['name'], 'type': p['type'],
                'transit_name': p.get('transit_name', 'N/A'),
                'transit_dist': p.get('transit_dist', 'N/A')
            })
            
        schedule.sort(key=lambda x: x['s'])
        # print("\nGenerated itinerary:\n")
        out_entries = []
        for item in schedule:
            s, e, name, typ = item['s'], item['e'], item['name'], item['type']

            label = "stay" # Default
            if typ.startswith("accommodation"):
                label = "stay"
            elif typ == 'travel':
                label = 'travel'
            else:
                label = "visit"
                
            # print(f"{fmt(s)} - {fmt(e)} | {name} ({label})")
            
            if typ != 'travel': 
                entry_type = "stay" if typ.startswith("accommodation") else "visit"
                transit_name = item['transit_name']
                transit_dist = item['transit_dist']
                try:
                    dist_str = f"{float(transit_dist):.2f}m"
                except:
                    dist_str = f"{transit_dist}" 
                    if transit_dist != "N/A":
                        dist_str += "m"
                out_entries.append(f"{name}, {entry_type} from {fmt(s)} to {fmt(e)}, nearest transit: {transit_name}, {dist_str} away")
        
        poi_list_str = "; ".join(out_entries)
        # print(f"\npoint_of_interest_list:\n{poi_list_str}")

    # print("---------------------------------------------------\n")
    
    return poi_list_str, (current_day_accom_name if has_accommodation else None)

full_itinerary = [
  {
    "day": 1,
    "current_city": "from Sacramento to Atlanta",
    "transportation": "Self-Driving from Sacramento to Atlanta, Duration: 2606 mins, Arrival Time: 19:30",
    "breakfast": "-",
    "attraction": "-",
    "lunch": "-",
    "dinner": "South City Kitchen Midtown, Atlanta",
    "accommodation": "Heart of city free parking walk to Marta train(T), Atlanta",
    "event": "-",
    "point_of_interest_list": "No feasible schedule found."
  },
  {
    "day": 2,
    "current_city": "Atlanta",
    "transportation": "-",
    "breakfast": "Cafe Agora, Atlanta",
    "attraction": "Piedmont Park, Atlanta; Atlanta Botanical Garden, Atlanta",
    "lunch": "La Tavola Trattoria, Atlanta",
    "dinner": "Murphy's Restaurant, Atlanta",
    "accommodation": "Heart of city free parking walk to Marta train(T), Atlanta",
    "event": "-",
    "point_of_interest_list": "Heart of city free parking walk to Marta train(T), stay from 08:00 to 08:30, nearest transit: WINDSOR ST SW @ RICHARDSON ST SW, 152.46m away; Cafe Agora, visit from 08:55 to 09:35, nearest transit: PEACHTREE ST @ PEACHTREE PL, 29.31m away; Piedmont Park, visit from 10:00 to 12:00, nearest transit: PIEDMONT AVE NE @ PRADO, 407.10m away; Atlanta Botanical Garden, visit from 12:25 to 14:25, nearest transit: PIEDMONT AVE NE @ THE PRADO, 229.39m away; La Tavola Trattoria, visit from 14:50 to 15:30, nearest transit: VIRGINIA AVE NE @ TODD RD NE, 27.36m away; Murphy's Restaurant, visit from 19:30 to 20:10, nearest transit: VIRGINIA AVE NE @ TODD RD NE, 29.86m away; Heart of city free parking walk to Marta train(T), stay from 20:35 to 08:00, nearest transit: WINDSOR ST SW @ RICHARDSON ST SW, 152.46m away"
  },
  {
    "day": 3,
    "current_city": "from Atlanta to Sacramento",
    "transportation": "Self-Driving from Atlanta to Sacramento, Duration: 2608 mins, Departure Time: 16:00",
    "breakfast": "Buttermilk Kitchen, Atlanta",
    "attraction": "Zoo Atlanta, Atlanta",
    "lunch": "Home Grown, Atlanta",
    "dinner": "-",
    "accommodation": "-",
    "event": "-",
    "point_of_interest_list": "Heart of city free parking walk to Marta train(T), stay from 08:00 to 08:30, nearest transit: WINDSOR ST SW @ RICHARDSON ST SW, 152.46m away; Buttermilk Kitchen, visit from 08:55 to 09:35, nearest transit: ROSWELL RD NE @ RICKENBACKER DR NE, 37.96m away; Zoo Atlanta, visit from 10:00 to 12:00, nearest transit: CHEROKEE AVE @ GRANT PARK PL, 195.14m away; Home Grown, visit from 13:35 to 14:15, nearest transit: MEMORIAL DR SE @ GIBSON ST SE, 49.17m away"
  }
]


# --- Run the scheduler for each day ---
# final_json = []
# last_day_accom_name = None
# transits = Transits()

# for day_plan in full_itinerary:
#     poi_schedule_str, current_day_accom_name = schedule_day(transits, day_plan, last_day_accom_name)

#     day_plan['point_of_interest_list'] = poi_schedule_str
#     final_json.append(day_plan)

#     last_day_accom_name = current_day_accom_name

# print("\n=== FINAL JSON OUTPUT ===\n")
# print(final_json)

# ----- END OF TESTING PURPOSES ONLY -----


def add_poi_list(folder, mode, model, iteration):
    transits = Transits()

    for j in range(iteration):
        print(j)
        path = f'{folder}/{mode}/{model}/{j+1}/plans/'
        file_path = os.path.join(path, 'plan_json.txt')

        if os.path.exists(file_path):
            with open(file_path, 'r', encoding="utf-8") as file:
                plan_json = file.read().strip()


            if not plan_json:
                print(f"Warning: Empty file {file_path}")
                continue

            try:
                plans = ast.literal_eval(plan_json)
            except Exception as e:
                print(f"Warning: Could not parse {file_path} - {e}")
                continue

            final_json = []
            last_day_accom_name = None
            for(idx, plan) in enumerate(plans):
                if('days' not in plan and 'day' not in plan):
                    continue
                poi_schedule_str, current_day_accom_name = schedule_day(transits, plan, last_day_accom_name)
                plan['event'] = "-"
                plan['point_of_interest_list'] = poi_schedule_str
                final_json.append(plan)
                last_day_accom_name = current_day_accom_name
            
            output_file_path =  os.path.join(path, 'plan_with_poi_json.txt')
            with open(output_file_path, 'w') as file:
                json.dump(final_json, file, indent=2)

if __name__ == "__main__":
    add_poi_list('output','5d','phi_nl', 324)
