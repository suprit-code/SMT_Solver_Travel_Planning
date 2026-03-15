import re, string, os, sys
import time
import json
import pdb
import openai
import argparse
import traceback

import pandas as pd
from pandas import DataFrame
import importlib
import tiktoken
from datetime import datetime
from tqdm import tqdm
from datasets import load_dataset
from z3 import *
from openai_func import *
from open_source_models import *
from typing import List, Dict, Any

# from langchain.chat_models import ChatOpenAI
from langchain.callbacks import get_openai_callback
# from langchain.llms.base import BaseLLM
# from langchain.prompts import PromptTemplate
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain.schema import (
#     AIMessage,
#     HumanMessage,
#     SystemMessage
# )

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


# OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
# GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']

actionMapping = {"FlightSearch":"flights","AttractionSearch":"attractions","GoogleDistanceMatrix":"googleDistanceMatrix","accommodationSearch":"accommodation","RestaurantSearch":"restaurants","CitySearch":"cities"}


def convert_to_int(real):
    out = ToInt(real) # ToInt(real + 0.0001)
    out += If(real == out, 0, 1)
    return out


def extract_spending_preference(user_persona):
    persona_parts = [part.strip() for part in user_persona.split(';')]
    for part in persona_parts:
        if part.startswith("Spending Preference:"):
            return part.split(":", 1)[1].strip()
    return "Economical Traveler"


def add_spending_preference_constraints(user_persona, code):
    spending_preference = extract_spending_preference(user_persona)
    if spending_preference == "Luxury Traveler":
        code += "\ns.maximize(spent)\n"   
    elif spending_preference == "Economical Traveler":
        code += "\ns.minimize(spent)\n"
    return code


def pipeline(query, user_persona, mode, model, index, model_version = None):
    path =  f'output/{mode}/{model}_nl/{index}/'
    # path =  f'output/{mode}/{model}_nl/{index}/'
    if not os.path.exists(path):
        os.makedirs(path)
        os.makedirs(path+'codes/')
        os.makedirs(path+'plans/')
    # setup
    with open('prompts/query_to_json.txt', 'r') as file:
        query_to_json_prompt = file.read()
    with open('prompts/constraint_to_step_nl_v2.txt', 'r') as file:
        constraint_to_step_prompt = file.read()
    with open('prompts/step_to_code_destination_cities.txt', 'r') as file:
        step_to_code_destination_cities_prompt = file.read()
    with open('prompts/step_to_code_departure_datesv2.txt', 'r') as file:
        step_to_code_departure_dates_prompt = file.read()
    with open('prompts/step_to_code_transportation_methods.txt', 'r') as file:
        step_to_code_transportation_methods_prompt = file.read()
    with open('prompts/step_to_code_flight.txt', 'r') as file:
        step_to_code_flight_prompt = file.read()
    with open('prompts/step_to_code_driving.txt', 'r') as file:
        step_to_code_driving_prompt = file.read()
    with open('prompts/step_to_code_restaurant.txt', 'r') as file:
        step_to_code_restaurant_prompt = file.read()
    with open('prompts/step_to_code_attraction_v2.txt', 'r') as file:
        step_to_code_attraction_prompt = file.read()
    with open('prompts/step_to_code_accommodation.txt', 'r') as file:
        step_to_code_accommodation_prompt = file.read()
    with open('prompts/step_to_code_budget.txt', 'r') as file:
        step_to_code_budget_prompt = file.read()
        
    CitySearch = Cities()
    # CitySearch.run('Texas', 'Seattle',["2022-03-10", "2022-03-11", "2022-03-12", "2022-03-13", "2022-03-14", "2022-03-15", "2022-03-16"])
    # pdb.set_trace()
    FlightSearch = Flights()
    AttractionSearch = Attractions()
    DistanceSearch = GoogleDistanceMatrix()
    AccommodationSearch = Accommodations()
    RestaurantSearch = Restaurants()
    s = Optimize()
    variables = {}
    times = []

    step_to_code_prompts = {
                            'Destination cities': step_to_code_destination_cities_prompt, 
                            'Departure dates': step_to_code_departure_dates_prompt,
                            'Transportation methods': step_to_code_transportation_methods_prompt,
                            'Flight information': step_to_code_flight_prompt,
                            'Driving information': step_to_code_driving_prompt,
                            'Restaurant information': step_to_code_restaurant_prompt,
                            'Attraction information': step_to_code_attraction_prompt,
                            'Accommodation information': step_to_code_accommodation_prompt,
                            'Budget': step_to_code_budget_prompt
                            }
    plan = ''
    plan_json = ''
    codes = ''
    success = False

    if(model == 'qwen'): qwen_llm = LLMWrapper("qwen")
    elif(model == 'phi'): phi_llm = LLMWrapper("phi")
    elif(model == 'codellama'): codellama_llm = LLMWrapper("codellama")
    elif(model == 'llama'): llama_llm = LLMWrapper("llama")

    try:
        # json generated for postprocess only, not used in inputs to LLMs
        if model == 'gpt': query_json = json.loads(GPT_response(query_to_json_prompt + '{' + query + '}\n' + 'JSON:\n', model_version).replace('```json', '').replace('```', ''))
        elif model == 'gemini' : query_json = json.loads(Gemini_response("You are JSON generator so only generate JSON" + query_to_json_prompt + '{' + query + '}\n' + 'JSON:\n').replace('```json', '').replace('```', ''))
        elif model == 'claude': query_json = json.loads(Claude_response(query_to_json_prompt + '{' + query + '}\n' + 'JSON:\n').replace('```json', '').replace('```', ''))
        elif model == 'mixtral': query_json = json.loads(Mixtral_response(query_to_json_prompt + '{' + query + '}\n' + 'JSON:\n', 'json').replace('```json', '').replace('```', '')) 
        elif model == 'qwen': query_json = json.loads(qwen_llm.generate("You are JSON generator so only generate JSON" + query_to_json_prompt + '{' + query + '}\n' + 'JSON:\n').replace('```json', '').replace('```', ''))
        elif model == 'phi': query_json = json.loads(phi_llm.generate("You are JSON generator so only generate JSON" + query_to_json_prompt + '{' + query + '}\n' + 'JSON:\n').replace('```json', '').replace('```', ''))
        elif model == 'llama' : query_json = json.loads(llama_llm.generate("You are JSON generator so only generate JSON" + query_to_json_prompt + '{' + query + '}\n' + 'JSON:\n').replace('```json', '').replace('```', ''))
        elif model == 'codellama' : query_json = json.loads(codellama_llm.generate("You are JSON generator so only generate JSON" + query_to_json_prompt + '{' + query + '}\n' + 'JSON:\n').replace('```json', '').replace('```', ''))
        else: ...
        
        with open(path+'plans/' + 'query.txt', 'w') as f:
            f.write(query)
        f.close()

        with open(path+'plans/' + 'query.json', 'w') as f:
            json.dump(query_json, f)
        f.close()

        start = time.time()
        if model == 'gpt': steps = GPT_response(constraint_to_step_prompt + query + '\n' + 'Steps:\n', model_version)
        elif model == 'gemini': steps = Gemini_response(constraint_to_step_prompt + query + '\n' + 'Steps:\n')
        elif model == 'claude': steps = Claude_response(constraint_to_step_prompt + query + '\n' + 'Steps:\n')
        elif model == 'mixtral': steps = Mixtral_response(constraint_to_step_prompt + query + '\n' + 'Steps:\n')
        elif model == 'qwen': steps = qwen_llm.generate(constraint_to_step_prompt + query + '\n' + 'Steps:\n')
        elif model == 'phi': steps = phi_llm.generate(constraint_to_step_prompt + query + '\n' + 'Steps:\n')
        elif model == 'llama' : steps = llama_llm.generate(constraint_to_step_prompt + "** Respond with steps only which start with # ** \n" + query + '\n' + 'Steps:\n')
        elif model == 'codellama' : steps = codellama_llm.generate(constraint_to_step_prompt + query + '\n' + 'Steps:\n')
        else: ...
        json_step = time.time()
        times.append(json_step - start)
        
        with open(path+'plans/' + 'steps.txt', 'w') as f:
            f.write(steps)
        f.close()

        steps = steps.split('\n\n')
        # pdb.set_trace()
        for step in steps:
            try: 
                lines = step.split('# \n')[1]
            except:
                lines = step.split('#\n')[1]
            prompt = ''
            step_key = ''
            for key in step_to_code_prompts.keys():
                if key in step.split('# \n')[0]:
                    prompt = step_to_code_prompts[key]
                    step_key = key

            # print(prompt +'\nRespond with python codes only, do not add \ in front of symbols like _ or *.\n Follow the indentation of provided examples carefully, indent after for-loops!\n' +lines)
                    
            start = time.time()
            if model == 'gpt': code = GPT_response(prompt + lines, model_version)
            elif model == 'gemini' : code = Gemini_response(prompt +'\nRespond with python codes only, do not add \ in front of symbols like _ or *.\n Follow the indentation of provided examples carefully, indent after for-loops!\n' +lines)
            elif model == 'claude': code = Claude_response(prompt + lines)
            elif model == 'mixtral': code = Mixtral_response(prompt +'\nRespond with python codes only, do not add \ in front of symbols like _ or *.\n Follow the indentation of provided examples carefully, indent after for-loops!\n' +lines, 'code') # '\nRespond json with python codes only\n' 
            elif model == 'qwen': code = qwen_llm.generate(prompt +'\nRespond with python codes only, do not add \ in front of symbols like _ or *.\n Follow the indentation of provided examples carefully, indent after for-loops!\n' +lines) # '\nRespond json with python codes only\n'
            elif model == 'phi': code = phi_llm.generate(prompt +'\nRespond with python codes only, do not add \ in front of symbols like _ or *.\n Follow the indentation of provided examples carefully, indent after for-loops!\n' +lines) # '\nRespond json with python codes only\n'
            elif model == 'llama' : code = llama_llm.generate(prompt +'\n ** Follow the indentation of provided examples carefully, indent after for-loops! ** \n' +lines) # '\nRespond json with python codes only\n'
            elif model == 'codellama' : code = codellama_llm.generate(prompt +'\nRespond with python codes only, do not add \ in front of symbols like _ or *.\n Follow the indentation of provided examples carefully, indent after for-loops!\n' +lines) # '\nRespond json with python codes only\n'
            else: ...

            step_code = time.time()
            times.append(step_code - start)
            code = code.replace('```python', '')
            code = code.replace('```', '')
            code = code.replace('\_', '_')
            
            if(step_key == 'Budget'):
                code = add_spending_preference_constraints(user_persona, code)
            
            if step_key != 'Destination cities': 
                if query_json['days'] == 3:
                    code = code.replace('\n', '\n    ')
                elif query_json['days'] == 5:
                    code = code.replace('\n', '\n            ')
                else:
                    code = code.replace('\n', '\n                ')

            codes += code + '\n'
            with open(path+'codes/' + f'{step_key}.txt', 'w') as f:
                f.write(code)
            f.close()

        with open('prompts/solve_{}.txt'.format(query_json['days']), 'r') as f:
            codes += f.read()
        with open(path+'codes/' + 'codes.txt', 'w') as f:
            f.write(codes)
        f.close()
        start = time.time()
        # exec(codes)
        exec_code = time.time()
        times.append(exec_code - start)
    except Exception as e:
        with open(path+'plans/' + 'error.txt', 'w') as f:
            f.write("Error message:\n")
            f.write(str(e) + "\n\n")
            # f.write(e.args)
            f.write("Full traceback:\n")
            f.write(traceback.format_exc())
        f.close()
    with open(path+'plans/' + 'time.txt', 'w') as f:
        for line in times:
            f.write(f"{line}\n")
    
def run_code(mode, user_mode, index):
    path =  f'output/{mode}/{user_mode}/{index}/'
        
    CitySearch = Cities()
    FlightSearch = Flights()
    AttractionSearch = Attractions()
    DistanceSearch = GoogleDistanceMatrix()
    AccommodationSearch = Accommodations()
    RestaurantSearch = Restaurants()
    s = Optimize()
    variables = {}
    success = False

    with open(path+'plans/' + 'query.json', 'r') as f:
        query_json = json.loads(f.read())
    f.close()
    with open(path+'codes/' + 'codes.txt', 'r') as f:
        codes = f.read()
    f.close()
    local_vars = locals()
    start = time.time()
    exec(codes, globals(), local_vars)
    exec_code = time.time()
    print('time taken -> ', exec_code - start)

if __name__ == '__main__':

    tools_list = ["flights","attractions","accommodations","restaurants","googleDistanceMatrix","cities"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--set_type", type=str, default="validation")
    parser.add_argument("--model_name", type=str, default="gpt") #'gpt', 'claude', 'mixtral', other models
    args = parser.parse_args()

    if args.set_type == 'validation':
        print('validation')
        query_data_list  = load_dataset('osunlp/TravelPlanner','validation')['validation']
    elif args.set_type == 'test':
        print('test')
        query_data_list  = load_dataset('osunlp/TravelPlanner','test')['test']
    elif args.set_type == '3d':
        print('3d')
        query_data_list = pd.read_csv("tripcraft_3day.csv")
    elif args.set_type == '5d':
        print('5d')
        query_data_list = pd.read_csv("tripcraft_5day.csv")
    elif args.set_type == '7d':
        print('7d')
        query_data_list = pd.read_csv("tripcraft_7day.csv")
    else:
        query_data_list  = load_dataset('osunlp/TravelPlanner','train')['train']
        # query_data_list = pd.read_csv("tripcraft_3day.csv")

    numbers = [i for i in range(1,len(query_data_list)+1)]
    with get_openai_callback() as cb:
        for number in tqdm(numbers[:]):
            path =  f'Tripcraft_output/{args.set_type}/{args.model_name}/{number}/plans/'
            if not os.path.exists(path + 'plan.txt'):
                if(number==314):
                    print(number)
                    # query = query_data_list[number-1]['query']
                    query = query_data_list['query'][number-1]
                    user_persona = query_data_list['persona'][number-1]
                    print(query)
                    print(user_persona)
                    result_plan = pipeline(query, user_persona, args.set_type, args.model_name, number, "gpt-4o") #'gpt', 'claude', 'mixtral' or other models
