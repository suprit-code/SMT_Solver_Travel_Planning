import pandas as pd
import numpy as np
from pandas import DataFrame
from typing import Optional
from utils.func import extract_before_parenthesis
from z3 import *


class Attractions:

    category_list = ['Boat Tours & Water Sports', 'Casinos & Gambling', 'Classes & Workshops', 
                    'Concerts & Shows', 'Events', 'Food & Drink', 'Fun & Games', 'Museums', 
                    'Nature & Parks', 'Nightlife', 'Other', 'Outdoor Activities', 'Shopping', 
                    'Sights & Landmarks', 'Spas & Wellness', 'Tours', 'Transportation', 
                    'Traveler Resources', 'Water & Amusement Parks', 'Zoos & Aquariums']

    def __init__(self, path='TripCraft_database/attraction/cleaned_attractions_final.csv'):
        self.path = path
        self.data = self.load_db()
        print(self.data.columns)
        print("Attractions v2 loaded.")

    def load_db(self):
        """ load database and feature analysis"""
        df = pd.read_csv(self.path).dropna()
        df = df.rename(columns={
            "name" : "Name", 
            "latitude" : "Latitude",
            "longitude" : "Longitude",
            "address" : "Address",
            "website" : "Website",
            "subcategories" : "category"
        })
        df['Phone'] = 00            #Putting a default value as this data is not available in dataset
        self.data = df[['Name','Latitude','Longitude','Address','Phone','Website',"City", "category"]]
        return self.data



    def run(self, city: str ) -> DataFrame:
        """Search for Accommodations by city and date."""
        results = self.data[self.data["City"] == city]
        # the results should show the index
        results = results.reset_index(drop=True)
        if len(results) == 0:
            return "There is no attraction in this city."
        return results  



    def run_for_all_cities(self, all_cities, cities: list ):
        """Builds a Z3 array mapping each city's index in all_cities to the number of attractions found in self.data (or -1 if no data)."""
        
        results = Array('attractions', IntSort(), IntSort())        # city attraction
        results_category_constraint = Array('attractions_category', IntSort(), ArraySort(IntSort(), IntSort(), BoolSort()))  # city [attraction category bool]

        for i, city in enumerate(cities):
            result = self.data[self.data["City"] == city]
            if len(result) != 0:
                # print('attraction', city, len(result), len(np.array(result)[:,1]))
                results = Store(results, all_cities.index(city), IntVal(len(np.array(result)[:,1])))
                result_flags = Array('category flags', IntSort(), IntSort(), BoolSort())
                
                for index in range(np.array(result).shape[0]):
                    category_types_list = np.array(result)[:,7]
                    for j, category in enumerate(Attractions.category_list):
                        result_flags = Store(result_flags, index, j, category in category_types_list[index])
                results_category_constraint = Store(results_category_constraint, all_cities.index(city), result_flags)

            else:
                results = Store(results, all_cities.index(city), -1)
        return results, results_category_constraint



    def get_info(self, info, i):
        """ Return the value from a Z3 Array { ArraySort(IntSort(), IntSort()) } at the given index.  """
        length = Select(info, i)
        return length

    def get_info_for_index(self, info_list, index):
        """ Return the value from a Z3 Array { ArraySort(IntSort(), IntSort()) } at the given index.  """
        return Select(info_list, index)

    def get_category_index(self, category):
        if isinstance(category, int):
            return [category]
        elif isinstance(category, str):
            category_lower = category.lower()
            for idx, cat in enumerate(Attractions.category_list):
                if category_lower in cat.lower():
                    return [idx]
        elif isinstance(category, list):
            indices = []
            for cat in category:
                cat_lower = cat.lower()
                for idx, c in enumerate(Attractions.category_list):
                    if cat_lower in c.lower():
                        indices.append(idx)
            return indices
        return -1

    def check_exists(self, attractions_category_info, city, attraction_index, category):
        category_idx = self.get_category_index(category)
        if(category_idx == -1 or len(category_idx) == 0):
            return BoolVal(True)
        exists = Select(Select(attractions_category_info, city), attraction_index, category_idx[0])
        return If(attraction_index !=-1, exists, BoolVal(False))

    def check_exists_any(
        self,
        attractions_category_info,
        city,
        attraction_index,
        categories: list
    ):
        """ Checks if any of the given categories exist for the specified attraction in the specified city. """
        categories_idx = self.get_category_index(categories)
        if categories_idx == -1 or len(categories_idx) == 0:
            return BoolVal(True)
        exists_conditions = []
        for category in categories_idx:
            exists = Select(Select(attractions_category_info, city), attraction_index, category)
            exists_conditions.append(exists)
        return If(attraction_index != -1, Or(*exists_conditions), BoolVal(False))


    def attraction_in_which_city(self, arrives, origin, cities, departure_dates, days):
        """ Determines, for each day, which city the traveler is in based on arrival times and departure dates, using Z3 arrays. """
        result = []
        origin = -1
        cities = [origin] + cities
        
        arrives_array = Array('arrives', IntSort(), RealSort())
        cities_array = Array('cities', IntSort(), IntSort())
        departure_dates_array = Array('departure_dates', IntSort(), IntSort())
        
        for index, arrive in enumerate(arrives):
            arrives_array = Store(arrives_array, index, arrive)
        for index, city in enumerate(cities):
            cities_array = Store(cities_array, index, city)
        for index, date in enumerate(departure_dates):
            departure_dates_array = Store(departure_dates_array, index, date)
        
        i = 0
        for day in range(days):
            arrtime = Select(arrives_array, i)
            result.append(If(day == Select(departure_dates_array, i), If(arrtime > 18, Select(cities_array, i), Select(cities_array, i+1)), Select(cities_array, i+1)))
            i += If(day == Select(departure_dates_array, i), 1, 0)
        print("Having attraction_in_which_city info for {} attractions".format(len(result)))
        return result



    def run_for_annotation(self,
            city: str,
            ) -> DataFrame:
        """Search for Accommodations by city and date."""
        results = self.data[self.data["City"] == extract_before_parenthesis(city)]
        # the results should show the index
        results = results.reset_index(drop=True)
        return results