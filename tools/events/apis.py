import pandas as pd
import numpy as np
from pandas import DataFrame
from typing import Optional
from utils.func import extract_before_parenthesis
from datetime import datetime
from z3 import *

class Events:
    def __init__(self, path='D:\\BTP\\Tripcraft\\ATP_database\\events\\events_cleaned.csv'):
        self.path = path
        
        self.data = pd.read_csv(self.path)[['name', 'url', 'dateTitle', 'streetAddress', 'segmentName', 'city']].dropna(
            subset=['name', 'url', 'dateTitle', 'streetAddress', 'segmentName', 'city']
        )

        # Keep only rows with valid date formats (dd-mm-yyyy)
        self.data = self.data[self.data['dateTitle'].str.match(r'^\d{2}-\d{2}-\d{4}$', na=False)]

        # Convert date format in the CSV to datetime for filtering
        self.data['dateTitle'] = pd.to_datetime(self.data['dateTitle'], format='%d-%m-%Y')
        # print("Events loaded.")

    def load_db(self):
        self.data = pd.read_csv(self.path)

    def run(self, city: str, date_range: list) -> pd.DataFrame:
        """
        Search for Events by city and date range.
        Parameters:
            city: City to filter events.
            date_range: List of two strings in 'yyyy-mm-dd' format representing start and end dates.
        Returns:
            Filtered DataFrame with events in the city within the given date range.
        """
        # Parse the input date range
        start_date = datetime.strptime(date_range[0], '%Y-%m-%d')
        end_date = datetime.strptime(date_range[-1], '%Y-%m-%d')
        
        # Filter by city and date range
        results = self.data[
            (self.data['city'] == city) &
            (self.data['dateTitle'] >= start_date) &
            (self.data['dateTitle'] <= end_date)
        ]
        
        
        if len(results) == 0:
            return "There are no events in this city for the given date range."
        
        return results
    

    def run_for_all_cities(self, 
            all_cities: list,
            cities: list,
            date_range : list
            ):
        
        segment_list = ['Music', 'Sports', 'Arts & Theatre', 'Film', 'Miscellaneous']
        start_date = datetime.strptime(date_range[0], '%Y-%m-%d')
        end_date = datetime.strptime(date_range[-1], '%Y-%m-%d')

        results = Array('events', IntSort(), IntSort(), IntSort()) # City date event
        results_segment_constraint = Array('events segment constraint', IntSort(), IntSort(), ArraySort(IntSort(), IntSort(), BoolSort())) # City date [event segment bool]

        for i, city in enumerate(cities):
            result = self.data[
                (self.data['city'] == city) &
                (self.data['dateTitle'] >= start_date) &
                (self.data['dateTitle'] <= end_date)
            ]

            if(len(result)!=0):
                for index in range(np.array(result).shape[0]):
                    date = (np.array(result)[:,2][index] - start_date).days
                    if date >= 0 and date < (end_date - start_date).days:
                        results = Store(results, all_cities.index(city), date, index)
                        
                        segment_types_list = np.array(result)[:,4][index]
                        # print(segment_types_list)
                        for j, segment in enumerate(segment_list):
                            if segment in segment_types_list:
                                results_segment_constraint = Store(results_segment_constraint, all_cities.index(city), date, Store(index, j, True))
                            else:
                                results_segment_constraint = Store(results_segment_constraint, all_cities.index(city), date, Store(index, j, False))
            else:
                for date in range((end_date - start_date).days):
                    results = Store(results, all_cities.index(city), date, -1)

        return results, results_segment_constraint
    


        
      
    def run_for_annotation(self, city: str) -> DataFrame:
        """Search for Accommodations by city."""
        results = self.data[self.data["city"] == extract_before_parenthesis(city)]
        # The results should show the index
        results = results.reset_index(drop=True)
        return results
