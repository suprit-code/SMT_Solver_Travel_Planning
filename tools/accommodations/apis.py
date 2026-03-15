import pandas as pd
import numpy as np
from pandas import DataFrame
from typing import Optional
from utils.func import extract_before_parenthesis
from z3 import *
import ast

#helper function
def extract_integer_price(pricing_string):
    try:
        pricing_dict = ast.literal_eval(pricing_string)
        price_str = pricing_dict.get('price')
        if price_str:
            return int(price_str.replace('$', ''))
    except:
        return None



class Accommodations:
    def __init__(self, path="TripCraft_database/accommodation/cleaned_listings_final_v2.csv"):
        self.path = path
        self.data = self.load_db()
        # print(self.data.columns)
        # print("Accommodations loaded.")



    def load_db(self):
        """ load database and feature analysis"""
        df = pd.read_csv(self.path).dropna()
        df['price'] = df['pricing'].apply(extract_integer_price)
        df = df.rename(columns={
            "name" : "NAME", 
            "roomType" : "room type",
            "house_rules" : "house_rules",
            "max_occupancy" : "maximum occupancy",
            "City" : "city" 
        })
        df['minimum nights'] = 1.0   #Putting a default value as this data is not available in dataset 
        self.data = df[['NAME','price','room type', 'house_rules', 'minimum nights', 'maximum occupancy', 'rating', 'city']]
        return self.data



    def run_search(self, city):
        """ Returns unique room types available in the given city """

        results = self.data[self.data["city"] == city]
        if len(results) == 0:
            return "There is no accommodation in this city."
        
        return np.unique(results['room type'].to_numpy())



    # Unique values in the 'roomType' column: ['entire_home' 'shared_room' 'private_room']
    def get_type_cities( self, type: str ) -> DataFrame:
        """Search for cities according to accommodations by type."""

        if type == 'shared room': type = 'shared_room'
        elif type == 'entire room': type = 'entire_home'
        elif type == 'private room': type = 'private_room'
        else: return f"Your input {type} is not valid. Please search for 'entire room', 'private room', or 'shared room'"

        results = self.data[self.data["room type"] == type]
        # the results should show the index
        results = results.reset_index(drop=True)
        if len(results) == 0:
            return f"There is no {type} in all cities."
        return np.unique(results['city'].to_numpy())



    def run(self, city: str ) -> DataFrame:
        """Search for accommodations by city."""
        results = self.data[self.data["city"] == city]
        if len(results) == 0:
            return "There is no accomodation in this city."
        
        return results



    def run_for_all_cities( self, all_cities: list, cities: list ):
        """
        For each city in `cities`, this function extracts accommodation data and stores it into Z3 Arrays (`results` and `results_hard_constraint`). 

        - `results` keeps numeric attributes: price, minimum nights, maximum occupancy, and the number of listings (length).
        - `results_hard_constraint` keeps boolean attributes for room types and house rules. 
        """
        types_rule_list = ['private_room', 'entire_home', 'shared_room', 'No visitors', 'No smoking', 'No parties', 'No children under 10', 'No pets']
        results = Array('accommodations', IntSort(), IntSort(), ArraySort(IntSort(), IntSort())) # (city index, attribute index) → values for price, minimum_nights, maximum_occupancy, length
        results_hard_constraint = Array('accommodations hard constraint', IntSort(), IntSort(), ArraySort(IntSort(), IntSort(), BoolSort())) # (city index, attribute index) → boolean arrays for room types and house rules
        
        for i, city in enumerate(cities):
            result = self.data[self.data["city"] == city]
            
            if len(result) != 0:
                # print('accommodations',city, len(result), len(np.array(result)[:,1]), np.array(result)[:,2], np.array(result)[:,3])
                # print('accommodations',city)                
                # import pdb; pdb.set_trace()
                price = Array('Price', IntSort(), IntSort())
                minimum_nights = Array('Minimum_nights', IntSort(), IntSort())
                maximum_occupancy = Array('Maximum_occupancy', IntSort(), IntSort())
                room_types = Array('Room_types', IntSort(), IntSort(), BoolSort())
                house_rules = Array('House_rules', IntSort(), IntSort(), BoolSort())
                length = Array('Length', IntSort(), IntSort())
                length = Store(length, 0, len(np.array(result)[:,1]))
                # import pdb; pdb.set_trace()

                for index in range(np.array(result).shape[0]):
                    # if np.array(result)[:,1][index] is not np.nan:
                    if not np.isnan(np.array(result)[:,1][index]):
                        price = Store(price, index, np.array(result)[:,1][index])
                    else:
                        price = Store(price, index, 0) #TODO
                    
                    # if np.array(result)[:,4][index] is not np.nan:
                    if not np.isnan(np.array(result)[:,4][index]):
                        minimum_nights = Store(minimum_nights, index, np.array(result)[:,4][index])
                    else:
                        minimum_nights = Store(minimum_nights, index, 0)
                    
                    # if np.array(result)[:,5][index] is not np.nan:
                    if not np.isnan(np.array(result)[:,5][index]):
                        maximum_occupancy = Store(maximum_occupancy, index, np.array(result)[:,5][index])
                    else:
                        maximum_occupancy = Store(maximum_occupancy, index, 10)
                    
                    room_types_list = np.array(result)[:,2][index]
                    house_rules_list = np.array(result)[:,3][index]
                    # print(room_types_list)
                    # print(house_rules_list)
                    for j in range(3):
                        # print(types_rule_list[j] in room_types_list)
                        room_types = Store(room_types, index, j, types_rule_list[j] in room_types_list)
                    for j in range(3,8):
                        house_rules = Store(house_rules, index, j, types_rule_list[j] in house_rules_list)
                
                results = Store(results, all_cities.index(city), 0, price)
                results = Store(results, all_cities.index(city), 1, minimum_nights)
                results = Store(results, all_cities.index(city), 2, maximum_occupancy)
                results = Store(results, all_cities.index(city), 3, length)
                results_hard_constraint = Store(results_hard_constraint, all_cities.index(city), 0, room_types)
                results_hard_constraint = Store(results_hard_constraint, all_cities.index(city), 1, house_rules)
            
            else:
                length = Array('Length', IntSort(), IntSort())
                length = Store(length, 0, -1)
                results = Store(results, all_cities.index(city), 3, length)
        return results, results_hard_constraint



    # ['Price', 'Minimum_nights', 'Maximum_occupancy', 'Length']
    def get_info(self, info, i, key):
        """ Retrieve a specific piece of accommodation data from the Z3 Array { Array('accommodations', IntSort(), IntSort(), ArraySort(IntSort(), IntSort())) }. """
        if key == 'Room_types' or key == 'House_rules':
            if key == 'Room_types':
                info_key = Select(info, i, 0)
            else:
                info_key = Select(info, i, 1)
            return info_key, None
        else:
            element = ['Price', 'Minimum_nights', 'Maximum_occupancy', 'Length']
            info_key = Select(info, i, element.index(key))
            info_length = Select(info, i, 3)
            length = Select(info_length, 0)
            return info_key, length



    def get_info_for_index(self, info_list, index):
        """ Return the value from a Z3 Array { ArraySort(IntSort(), IntSort()) } at the given index.  """
        return Select(info_list, index)



    def check_exists(self, type, accommodation_list, index):
        """ Check whether a given room type or house rule exists for an accommodation at the specified index. """
        if type == 'Shared room': type = 'shared_room'
        elif type == 'Entire home/apt': type = 'entire_home'
        elif type == 'Private room': type = 'private_room'

        types_rule_list = ['private_room', 'entire_home', 'shared_room', 'No visitors', 'No smoking', 'No parties', 'No children under 10', 'No pets']
        exists = Select(accommodation_list, index, types_rule_list.index(type))
        return If(index != -1, exists, BoolVal(False))



    def run_for_annotation(self, city: str ) -> DataFrame:
        """Search for accommodations by city."""
        results = self.data[self.data["city"] == extract_before_parenthesis(city)]
        return results