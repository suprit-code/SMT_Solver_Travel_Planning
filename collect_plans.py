import json
import pdb
import os.path
import ast
import pandas as pd

def collect_plans(mode, model):
    if mode == '3d':
        index = 344
    elif mode == '5d':
        index = 324
    elif mode == '7d':
        index = 332
    else:
        index = 1000
    plan_list = []
    for i in range(index):
        print(i)
        path =  f'output/{mode}/{model}/{i+1}/plans/'
        plan_list_single = []
        if os.path.exists(path + 'plan_with_poi_json.txt'):
            with open(path + 'plan_with_poi_json.txt', 'r') as file:
                plan_json = file.read()
                if plan_json == '':

                    if mode == '3d':
                        query_data_list = pd.read_csv("tripcraft_3day.csv")
                    elif mode == '5d':
                        query_data_list = pd.read_csv("tripcraft_5day.csv")
                    elif mode == '7d':
                        query_data_list = pd.read_csv("tripcraft_7day.csv")

                    if os.path.exists(path + 'query.txt'):
                        with open(path + 'query.txt', 'r') as file:
                            query = file.read()
                    else:
                        query = query_data_list.iloc[i]['query']

                    JSON = query_data_list.iloc[i].to_dict()

                    JSON['local_constraint'] = ast.literal_eval(JSON['local_constraint'])

                    entry = {"idx": i+1, "query": query, "plan": None, "JSON": JSON}
                    plan_list.append(entry)
                else:
                    plan_list_single = json.loads(plan_json)
                    
                    if mode == '3d':
                        query_data_list = pd.read_csv("tripcraft_3day.csv")
                    elif mode == '5d':
                        query_data_list = pd.read_csv("tripcraft_5day.csv")
                    elif mode == '7d':
                        query_data_list = pd.read_csv("tripcraft_7day.csv")

                    if os.path.exists(path + 'query.txt'):
                        with open(path + 'query.txt', 'r') as file:
                            query = file.read()
                    else:
                        query = query_data_list.iloc[i]['query']

                    JSON = query_data_list.iloc[i].to_dict()

                    # print(JSON['local_constraint'])
                    JSON['local_constraint'] = ast.literal_eval(JSON['local_constraint'])
                    # print(type(JSON['local_constraint']))
                    
                    entry = {"idx": i+1, "query": query, "plan": plan_list_single, "JSON": JSON, "persona": JSON["persona"]}
                    plan_list.append(entry)

    with open(f'output/{mode}_{model}_plan.jsonl', 'w') as outfile:
        for entry in plan_list:
            json.dump(entry, outfile)
            outfile.write('\n')

def check_plans(mode, model):
    if mode == '3d':
        index = 344
    elif mode == '5d':
        index = 324
    elif mode == '7d':
        index = 332
    else:
        index = 1000
    plan_list = []
    count = 0
    for i in range(index):
        path =  f'Tripcraft_output/{mode}/{model}/{i+1}/plans/'
        if not os.path.exists(path + 'plan.txt'):
            print(i+1)
            count+=1
    print('total', count)


if __name__ == '__main__':
    collect_plans('3d', 'phi_nl')
