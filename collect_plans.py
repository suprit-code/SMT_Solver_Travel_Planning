import json
import pdb
import os.path
import ast
import pandas as pd

def collect_plans(BASE_PATH, mode, model):
    if mode == '3d':
        index = 344
        query_data_list = pd.read_csv("tripcraft_3day.csv")
    elif mode == '5d':
        index = 324
        query_data_list = pd.read_csv("tripcraft_5day.csv")
    elif mode == '7d':
        index = 332
        query_data_list = pd.read_csv("tripcraft_7day.csv")
    else:
        index = 344
        query_data_list = pd.read_csv("tripcraft_3day.csv")
        
    plan_list = []
    for i in range(index):
        print(i)
        path =  f'{BASE_PATH}/{mode}/{model}/{i+1}/plans/'

        if os.path.exists(path + 'query.txt'):
            with open(path + 'query.txt', 'r', encoding='utf-8') as file:
                query = file.read()
        else:
            query = query_data_list.iloc[i]['query']

        JSON = query_data_list.iloc[i].to_dict()
        # print(JSON['local_constraint'])
        JSON['local_constraint'] = ast.literal_eval(JSON['local_constraint'])
        # print(type(JSON['local_constraint']))


        plan_list_single = []
        if os.path.exists(path + 'plan_with_poi.txt'):
            with open(path + 'plan_with_poi.txt', 'r', encoding='utf-8') as file:
                plan_json = file.read()
                if plan_json == '':
                    entry = {"idx": i+1, "query": query, "plan": "", "JSON": JSON, "persona": JSON["persona"]}
                    plan_list.append(entry)
                else:
                    plan_list_single = json.loads(plan_json)
                    entry = {"idx": i+1, "query": query, "plan": plan_list_single, "JSON": JSON, "persona": JSON["persona"]}
                    plan_list.append(entry)
        else:
            entry = {"idx": i+1, "query": query, "plan": "", "JSON": JSON, "persona": JSON["persona"]}
            plan_list.append(entry)

    with open(f'{BASE_PATH}/{mode}_{model}_plan.jsonl', 'w', encoding='utf-8') as outfile:
        for entry in plan_list:
            json.dump(entry, outfile)
            outfile.write('\n')

def check_plans(BASE_PATH, mode, model):
    if mode == '3d':
        index = 344
    elif mode == '5d':
        index = 324
    elif mode == '7d':
        index = 332
    else:
        index = 344
    plan_list = []
    count = 0
    for i in range(index):
        path =  f'{BASE_PATH}/{mode}/{model}/{i+1}/plans/'
        if not os.path.exists(path + 'plan.txt'):
            print(i+1)
            count+=1
    print('total', count)


if __name__ == '__main__':
    collect_plans('output', '3d', 'phi_nl')
