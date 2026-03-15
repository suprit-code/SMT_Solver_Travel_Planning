import pandas as pd
import numpy as np
from pandas import DataFrame
from typing import Optional
from utils.func import extract_before_parenthesis
from z3 import *

class Transits:
    def __init__(self, path="TripCraft_database/public_transit_gtfs/all_poi_nearest_stops.csv"):
        self.path = path
        self.data = self.load_db()
        # print(self.data.columns)
        # print("Transits Loaded.")


    def load_db(self):
        """ load database and feature analysis"""
        df = pd.read_csv(self.path).dropna()
        return df[["City", "State", "PoI", "nearest_stop_name", "nearest_stop_latitude", "nearest_stop_longitude", "nearest_stop_distance"]]



    def run(self, city : str, poi: str = None) -> pd.Series:
        """Search for nearest public transit stop by city and point of interest."""
        if poi is None:
            results = self.data[self.data["City"] == city]
        else:
            results = self.data[(self.data["City"] == city) & (self.data["PoI"] == poi)]
        # the results should show the index
        results = results.reset_index(drop=True)
        if len(results) == 0:
            return None
        return results

