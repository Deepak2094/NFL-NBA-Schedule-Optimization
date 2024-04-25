""" ---------------- NBA Mileage Heuristic ----------------"""

# Importing required modules
import time
from copy import deepcopy

import gurobipy as grb
from haversine import haversine, Unit
import csv

NBA = grb.read("../Inputs/Full_NBA_Model.lp")
NBA.read('../Inputs/NBA_Final_Solution.sol')
NBA.setParam('SolutionLimit', 1)
NBA.optimize()

# Reading the csv data files
Matchups_path = "../Inputs/matchUps_2020.csv"
Stadium_path = "../Inputs/stadium_avail_2020.csv"
Teamdata_path = "../Inputs/team_data_2020.csv"

# Reading the data to a List
Matchups_data = []
with open(Matchups_path, "r") as f:
    Matchups = csv.reader(f)
    next(Matchups)
    for rows in Matchups:
        Matchups_data.append(tuple(rows))

Stadium_data = []
with open(Stadium_path, "r") as f:
    Stadium = csv.reader(f)
    for rows in Stadium:
        Stadium_data.append(rows)

Teamdata_data = []
with open(Teamdata_path, "r") as f:
    Teamdata = csv.reader(f)
    next(Teamdata)
    for rows in Teamdata:
        Teamdata_data.append(rows)

Home_Teams = list(set([i[0] for i in Matchups_data]))
Away_Teams = list(set([i[1] for i in Matchups_data]))

Stadium_dates = {}
for rows in Stadium_data:
    Stadium_dates[rows[0]] = [str(dates) for dates in rows[1:] if dates != ""]

Team_Metrics = {}
for rows in Teamdata_data:
    Team_Metrics[rows[1]] = [Metrics for Metrics in rows[2:]]

Data_Dict = {"Teams": Home_Teams, "Matchups": Matchups_data,
             "Stadium_dates": Stadium_dates, "Team_Metrics": Team_Metrics}

NBA_vars = NBA.getVars()

Games = {}
NBA_vars = [v for v in NBA.getVars() if v.varname[0] == 'x']
for v in NBA_vars:
    variables = v.varName.split(',')
    variables[0] = variables[0][2:]
    variables[3] = variables[3][:-1]
    Games[variables[0], variables[1], variables[2], variables[3]] = v.x

Schedule = {}
for k, v in Games.items():
    if v == 1:
        Schedule[k] = v

Solution = grb.tuplelist(Schedule.keys())

Current_Schedule = Schedule.keys()

# Team Location - Lat and Longitude
Team_loc = {}
for k, v in Data_Dict["Team_Metrics"].items():
    Team_loc[k] = (float(v[0].replace(" ", "")), float(v[1].replace(" ", "")))

# Calculating the distance for each Team with respect to others
Distance = {}
for h in Data_Dict["Teams"]:
    for a in Data_Dict["Teams"]:
        Distance[h, a] = haversine((Team_loc[h][0], Team_loc[h][1]), (Team_loc[a][0], Team_loc[a][1]), unit=Unit.MILES)

Team_standby = {}
for t in Data_Dict["Teams"]:
    Team_standby[t] = list(
        map(str, sorted(set(int(i) for i in Data_Dict["Stadium_dates"][t]) - set(
            int(j[3]) for j in Current_Schedule if j[0] == t))))

Team_availability = {}
for t in Data_Dict["Teams"]:
    Team_availability[t] = []
    for d in [str(i) for i in range(1, 177)]:
        if d not in [z[3] for z in Current_Schedule if z[0] == t] and d not in [z[3] for z in Current_Schedule if
                                                                                z[1] == t]:
            Team_availability[t].append(d)


# Creating New schedule
def New_schedule(Current_Schedule):
    New_schedule = {}
    for t in Data_Dict["Teams"]:
        New_schedule[t] = []
        for d in [str(i) for i in range(1, 177)]:
            if d in Data_Dict["Stadium_dates"][t]:
                if d in [i[3] for i in Current_Schedule if i[0] == t]:
                    for i in Current_Schedule:
                        if i[0] == t and d == i[3]:
                            New_schedule[t].append(('h', i[1], i[2]))
                else:
                    New_schedule[t].append('X')
            else:
                if d in [i[3] for i in Current_Schedule if i[1] == t]:
                    for i in Current_Schedule:
                        if i[1] == t and d == i[3]:
                            New_schedule[t].append(('a', i[0], i[2]))
                else:
                    New_schedule[t].append('')
    return New_schedule


New_schedule = New_schedule(Current_Schedule)

# Calculating Travel distance based on the current schdeule before heuristic optimization
Travel_dist = {}
j = 0
for t in Data_Dict["Teams"]:
    y = t
    for i in New_schedule[t]:
        if i not in ["", "X"]:
            if i[0] == 'a':
                j = Distance[(y, i[1])] + j
                y = i[1]
            else:
                j = Distance[(y, t)] + j
                y = t
                j = Distance[(y, t)] + j
    Travel_dist[t] = j
    j = 0


def temp_dist(temp_schedule):
    temp_cost = {}
    j = 0
    for t in temp_schedule:
        y = t
        for i in temp_schedule[t]:
            if i not in ["", "X"]:
                if i[0] == 'a':
                    j = Distance[(y, i[1])] + j
                    y = i[1]
                else:
                    j = Distance[(y, t)] + j
                    y = t
                    j = Distance[(y, t)] + j
        temp_cost[t] = j
        j = 0
    return temp_cost


def temp_schedule(t1, t2, m, d):
    keys = [t1, t2]
    values = [deepcopy(New_schedule[t1]), deepcopy(New_schedule[t2])]
    temp_schedule = dict(zip(keys, values))
    if ('a', t2, m) in temp_schedule[t1]:
        k = temp_schedule[t1].index(('a', t2, m))
        if d in Data_Dict["Stadium_dates"][t1]:
            temp_schedule[t1][k] = 'X'
            temp_schedule[t1].insert(int(d) - 1, ('a', t2, m))
        else:
            temp_schedule[t1][k] = ''
            temp_schedule[t1].insert(int(d) - 1, ('a', t2, m))
    if ('h', t1, m) in temp_schedule[t1]:
        n = temp_schedule[t2].index(('h', t1, m))
        if d in Data_Dict["Stadium_dates"][t2]:
            temp_schedule[t2][n] = 'X'
            temp_schedule[t2].insert(int(d) - 1, ('h', t1, m))
        else:
            temp_schedule[t2][n] = ''
            temp_schedule[t2].insert(int(d) - 1, ('h', t1, m))

    temp = temp_dist(temp_schedule)
    if temp[t1] < Travel_dist[t1] and temp[t2] < Travel_dist[t2]:
        oName = 'x(%s, %s, %s, %s)' % (t2, t1, m, str(k + 1))
        tName = 'x(%s, %s, %s, %s)' % (t2, t1, m, d)
        oNBAVar = NBA.getVarByName(oName)
        oNBAVar.ub = 0
        tNBAVar = NBA.getVarByName(tName)
        tNBAVar.lb = 1
    return temp_schedule, temp


# """ Heuristic to Reduce Distance Travelled """
NBA.setParam("logtoconsole", 0)
start_time = time.time()
string = "{0:<12}{1:<12}"
i = 0
Repeat = True
while Repeat:
    header = string.format("Iteration", "RunTime")
    print(header)
    Repeat = False
    for t in Data_Dict["Teams"]:
        for a in [x for x in New_schedule[t] if x not in ['', 'X'] and x[0] == 'a']:
            for d in Team_standby[a[1]]:
                if d in Team_availability[t]:
                    temp_sch, temp_c = temp_schedule(t, a[1], a[2], d)
                    NBA.update()
                    NBA.optimize()
                    message = string.format(i, round(time.time() - start_time, 2))  # Output Message
                    print(message)
                    if NBA.Status != grb.GRB.INFEASIBLE:
                        New_schedule[t] = temp_sch[t]
                        New_schedule[a[1]] = temp_sch[a[1]]
                        Travel_dist[t] = temp_c[t]
                        Travel_dist[a[1]] = temp_c[a[1]]
                        repeat = True
                    elif time.time() - start_time > 600:
                        break
                    i += 1

NBA.setParam('SolutionLimit', 1)
NBA.write('../Outputs/NBA_Mileage.lp')
NBA.optimize()
NBA.write('../Outputs/NBA_Mileage.sol')


List = []

for i in range(1001):
    List.append(i)

print(List)

List = [ for i in range(1001)]


List = [1, 2, 3, 4, 5]
tUPLE = (1, 2, 3, 4)

R_1_1 = 9
R_1_2 = 8
R_1_3 = 7
R_1_3 = 7
R_1_3 = 7
R_1_3 = 7
R_1_3 = 7

Dict_for_r = {(1,1): 9, (1, 2): 8, }

