import random
import subprocess
from numpy import median
import sys
import benchs
import ins
import math

gmean = lambda X : math.exp(sum([math.log(x) for x in X])/len(X))

def poss(n,c):
    """if we wanted to use 'chunks', this is the function to compute number of possibilities
    smallest: poss(38,6) =  3283200"""
    return math.factorial(n/c) * (n * math.factorial(c-1))


def specialMedian(d):
    d = sorted(d)
    length = len(d)
    split = lambda a,b: (a[0]/2.0 + b[0]/2.0 , map(lambda x,y: x/2.0 + y/2.0, a[1], b[1]))
    if length %2:
        return d[(length-1)/2]
    else:
        return split( d[(length/2)-1], d[length/2])

def evaluate_perm(opcode_perm,benchmarks,bench_arguments,papi=False):
    o = open('lins.c','w')
    for opcode in opcode_perm:
        o.write(ins.opcodes[opcode])
    o.close()
    #compile - takes about 0.5s to compile lvm.c and link
    if papi:
        target = "linuxpapi"
    else:
        target = "linux"
    subprocess.call(["make",target], stderr=subprocess.PIPE,stdout=subprocess.PIPE,close_fds=True) #FIXBACK
    results = []
    for bench in benchmarks:
    #run
        times = []
        papis = []
        for x in range(0,15):
            lua_process = subprocess.Popen(["./lua", "benchmarks/"+bench,bench_arguments[bench]], stderr=subprocess.PIPE,stdout=subprocess.PIPE, close_fds=True)
            _,stderr = lua_process.communicate()
            if papi:
                data = [float(x) for x in stderr.split()]
                papi_values,time = data[:-1], data[-1]
                papis.append(papi_values)
                times.append(time)
            else:
                times.append(float(stderr))
        if papi:
            results.append(([median(x) for x in zip(*papis)],median(times)))
        else:
            results.append(median(times))
    return results
    
memo = {}
def evaluate_perm_memo(opcode_perm):
    if opcode_perm in memo:
        return memo[opcode_perm]
    else:
        t = evaluate_perm(opcode_perm)
        memo[opcode_perm] = t
        return t

# def best_first():
#     sort_dict = lambda d: sorted(d,key=lambda x:-d[x])
#     benchmark  = benchs.bench[0]
#     order = sort_dict(benchs.freq[benchmark])
#     for op in ins.opcode_names:
#         if not op in order:
#             order.append(op)
#     results = evaluate_perm(tuple(order),benchs.bench,benchs.arguments)
#     print results

def fillOrderAndEvaluate(order):
    for op in ins.opcode_names:
        if not op in order:
            order.append(op)
    results = evaluate_perm(tuple(order),benchs.bench,benchs.arguments)
    return results    

def best_first(benchmark):
    sort_dict = lambda d: sorted(d,key=lambda x:-d[x])
    order = sort_dict(benchs.freq[benchmark])
    return fillOrderAndEvaluate(order)

def best_first_all():
    r = {}
    for b in benchs.bench:
        if b in benchs.freq:
            r[b] = best_first(b)
    return r

def graph_select(bench):
    import brun
    global Node
    from brun import Node
    handle = open('./benchmarks/%s.graph.pickle'%bench)
    order = brun.getSchedule(handle)
    return fillOrderAndEvaluate(order)

def graph_select_all():
    r = {}
    for x in benchs.bench[:6]:
        r[x] = graph_select(x)
    return r

def monte_carlo(filename):
    random_ins = ins.opcode_names
    allPerms = {}

    try:
        for i in range(500):
            random.shuffle(random_ins)
            results = evaluate_perm(tuple(random_ins),benchs.bench,benchs.arguments)
            allPerms[tuple(random_ins)] = results
            outfile = open(filename,'a')
            for r in results:
                outfile.write(str(r)+"\t")
            outfile.write('\n')
            outfile.close()
            print results
            sys.stdout.flush()
        open(filename+'.full','w').write(str(allPerms))

    except:
        open(filename+'.full','w').write(str(allPerms))


def monte_carlo_single_with_papi(filename):
    random_ins = ins.opcode_names
    allPerms = {}
    import pickle
    try:
        for i in range(500):
            random.shuffle(random_ins)
            result = evaluate_perm(tuple(random_ins),benchs.bench[2:3],benchs.arguments,papi=True)[0]
            print result
            sys.stdout.flush()
            allPerms[tuple(random_ins)] = result
        open(filename+'.full','w').write(str(allPerms))
        pickle.dump(allPerms,open(filename+'.full.pickle','w'))
    except:
        open(filename+'.full','w').write(str(allPerms))
        pickle.dump(allPerms,open(filename+'.full.pickle','w'))
        raise


def random_swap(opcode_perm):
    t = list(opcode_perm)
    i1 = i2 = 0
    while i1 == i2:
        i1 = random.randrange(len(opcode_perm))
        i2 = random.randrange(len(opcode_perm))
    t[i1], t[i2] = t[i2], t[i1]
    return tuple(t)

def evaluate_perm_gspeedup(opcode_perm,benchmarks,bench_arguments,baseline):
    times = evaluate_perm(opcode_perm,benchmarks,bench_arguments)
    speedups = [baseline[i]/float(y) for i,y in enumerate(times)]
    return gmean(speedups)

def sa_should_accept(delta,temperature,k):
    merit = math.exp((delta)/(k*temperature))
    # if current_value < candidate_cost:
    #     print "merit: %.3f\tdelta: %.3f\tk: %.3f temp: %.3f" %(merit,current_value-candidate_cost,k,temperature)
    return (delta > 0) or (merit  > random.random())
    

def simulated_annealing_all(filename,cooling_steps=15,steps_per_temp=50,cooling_fraction=0.5,k=1,):
    baseline = benchs.baselines['mclovin_reorder']
    temperature = 1
    allPerms = {}
    current_perm = tuple(ins.opcode_names)
    current_value = evaluate_perm_gspeedup(current_perm,benchs.bench,benchs.arguments,baseline)
    for _ in range(cooling_steps):
        temperature = temperature * cooling_fraction
        for _ in range(steps_per_temp):
            possible_solution = random_swap(current_perm)
            possible_solution_merit = evaluate_perm_gspeedup(possible_solution,benchs.bench,benchs.arguments,baseline)
            delta = possible_solution_merit - current_value
            if sa_should_accept(delta,temperature,k):
                current_value = possible_solution_merit
                current_perm = possible_solution
                allPerms[current_perm] = current_value
            outfile = open(filename,'a')
            outfile.write(str(current_value)+"\n")
            outfile.close()

    open(filename+'.full','w').write(str(allPerms))


def simulated_annealing_indiv(filename,cooling_steps=15,steps_per_temp=50,cooling_fraction=0.5,k=1):
    allData = []
    allPerms = []
    for bmark in benchs.bench:
        thisBresults = []
        thisBperms = {}
        temperature = 1
        current_perm = tuple(ins.opcode_names)
        current_value = evaluate_perm(current_perm,[bmark],benchs.arguments)[0]
        for _ in range(cooling_steps):
            temperature = temperature * cooling_fraction
            for _ in range(steps_per_temp):
                possible_solution = random_swap(current_perm)
                possible_solution_cost = evaluate_perm(possible_solution,[bmark],benchs.arguments)[0]
                delta = current_value - possible_solution_cost
                if sa_should_accept(delta,temperature,k):
                    current_value = possible_solution_cost
                    current_perm = possible_solution
                    thisBperms[current_perm] = current_value
                thisBresults.append(current_value)
        allData.append(thisBresults)
        allPerms.append(thisBperms)

    open(filename,'w').write(str(allData))
    open(filename+'.full','w').write(str(allPerms))


def stoc_hill_climb_all(filename,max_iters=750):
    b = benchs.bench[:1] #TEST IT WITH FIRST BENCHMARK!
    baseline = benchs.baselines['zooey_reorder']
    allPerms = {}
    current_perm = tuple(ins.opcode_names)
    current_value = evaluate_perm_gspeedup(current_perm,b,benchs.arguments,baseline)
    best_value = current_value
    notImproved = 0
    for _ in range(max_iters):
        if notImproved >= 100:
            print 'restarting'
            notImproved = 0
            t = list(current_perm)
            random.shuffle(t)
            current_perm = tuple(t)
            current_value = evaluate_perm_gspeedup(current_perm,b,benchs.arguments,baseline)
            best_value = current_value
        possible_solution = random_swap(current_perm)
        possible_solution_merit = evaluate_perm_gspeedup(possible_solution,b,benchs.arguments,baseline)
        delta = possible_solution_merit - current_value
        deltaFromBest = possible_solution_merit - best_value
        if delta > -0.003 and deltaFromBest > -0.003:       #  if possible_solution_merit >= current_value: #maximise speedup
            current_perm = possible_solution
            current_value = possible_solution_merit
            allPerms[current_perm] = current_value
            if current_value > best_value:
                best_value = current_value
                notImproved = 0
        outfile = open(filename,'a')
        outfile.write(str(current_value)+"\n")
        outfile.close()  
    open(filename+'.full','w').write(str(allPerms))

def stoc_hill_climb_indiv(filename,max_iters=750):
    allData = []
    allPerms = []
    for bmark in benchs.bench:
        thisBresults = []
        thisBperms = {}
        current_perm = tuple(ins.opcode_names)
        current_value = evaluate_perm(current_perm,[bmark],benchs.arguments)[0]
        best_value = current_value
        notImproved = 0
        for _ in range(max_iters):
            if notImproved >= 100:
                print 'restarting'
                notImproved = 0
                t = list(current_perm)
                random.shuffle(t)
                current_perm = tuple(t)
                current_value = evaluate_perm(current_perm,[bmark],benchs.arguments)[0]
                best_value = current_value
            possible_solution = random_swap(current_perm)
            possible_solution_cost = evaluate_perm(possible_solution,[bmark],benchs.arguments)[0]
            delta = current_value - possible_solution_cost
            deltaFromBest = best_value - possible_solution_cost
            notImproved +=1
            if delta > -0.003 and deltaFromBest > -0.003:
                current_perm = possible_solution
                current_value = possible_solution_cost
                thisBperms[current_perm] = current_value
                if current_value < best_value:
                    best_value = current_value
                    notImproved = 0
            thisBresults.append(current_value)
        allData.append(thisBresults)
        allPerms.append(thisBperms)

    open(filename,'w').write(str(allData))
    open(filename+'.full','w').write(str(allPerms))


def stoc_hill_climb_single(max_iters=750):
    current_perm = tuple(ins.opcode_names)
    current_value = evaluate_perm(current_perm,benchs.bench[:1],benchs.arguments)[0]
    best_value = current_value
    notImproved = 0
    for _ in range(max_iters):
        if notImproved >= 100:
            print 'restarting'
            notImproved = 0
            t = list(current_perm)
            random.shuffle(t)
            current_perm = tuple(t)
            current_value = evaluate_perm(current_perm,benchs.bench[:1],benchs.arguments)[0]
            best_value = current_value
        possible_solution = random_swap(current_perm)
        possible_solution_cost = evaluate_perm(possible_solution,benchs.bench[:1],benchs.arguments)[0]
        delta = current_value - possible_solution_cost
        deltaFromBest = best_value - possible_solution_cost
        notImproved +=1
        if delta > -0.003 and deltaFromBest > -0.003:
            current_perm = possible_solution
            current_value = possible_solution_cost
            if current_value < best_value:
                best_value = current_value
                notImproved = 0
        outfile = open('stoc_hill_climbing.times','a')
        outfile.write(str(current_value)+"\n")
        outfile.close()
                
def getBaseline():
    return evaluate_perm(tuple(ins.opcode_names),benchs.bench,benchs.arguments)


def checkFile():
    allPerms = eval(open('monte_carlo_mclovin_fann.full').read())
    for perm in allPerms:
        print "new:",evaluate_perm(perm,benchs.bench[:1],benchs.arguments)[0], "stored:", allPerms[perm]

def main():


    #monte_carlo_single_with_papi(sys.argv[1])

    #monte_carlo(sys.argv[1])

    #getBranches(sys.argv[1])

    #simulated_annealing_all('simulated_annealing_all',cooling_fraction=0.7,k=0.3)

    #simulated_annealing_indiv('simulated_annealing_indiv',cooling_fraction=0.7,k=0.3)


    #stoc_hill_climbing_all('stoc_hill_climbing_all')

    #stoc_hill_climbing_indiv('stoc_hill_climbing_indiv')


    #print graph_select_all()

    print best_first_all()

if __name__ == "__main__":
    main()



# >>> print best_order
# ('TAILCALL', 'CALL', 'LE', 'UNM', 'DIV', 'TESTSET', 'FORLOOP', 'VARARG', 'SETUPVAL', 'TEST', 'LOADK', 'MOVE', 'CONCAT', 'SETTABLE', 'SETGLOBAL', 'GETTABLE', 'MUL', 'SUB', 'CLOSE', 'FORPREP', 'POW', 'SELF', 'GETGLOBAL', 'LOADBOOL', 'NEWTABLE', 'GETUPVAL', 'TFORLOOP', 'LOADNIL', 'SETLIST', 'ADD', 'NOT', 'JMP', 'MOD', 'LEN', 'RETURN', 'LT', 'EQ', 'CLOSURE')
# >>> print evaluate_perm(best_order) #fannkuch
# 0.698841
#(monte-carlo n=3000)



#('FORPREP', 'NEWTABLE', 'SELF', 'DIV', 'MOVE', 'CALL', 'CLOSURE', 'MUL', 'JMP', 'CLOSE', 'SUB', 'SETGLOBAL', 'GETTABLE', 'TFORLOOP', 'LT', 'SETLIST', 'GETGLOBAL', 'NOT', 'SETTABLE', 'VARARG', 'GETUPVAL', 'SETUPVAL', 'TEST', 'LEN', 'POW', 'FORLOOP', 'LOADK', 'LOADBOOL', 'ADD', 'RETURN', 'LOADNIL', 'UNM', 'TESTSET', 'TAILCALL', 'LE', 'MOD', 'CONCAT', 'EQ')
#15645393.0 branch mispredictions
#(monte-carlo n=999)


# >>> print best_order
# ('SUB', 'SETGLOBAL', 'ADD', 'SETTABLE', 'LOADBOOL', 'SETLIST', 'UNM', 'FORPREP', 'MOD', 'EQ', 'DIV', 'NEWTABLE', 'NOT', 'MUL', 'CLOSURE', 'CLOSE', 'MOVE', 'LOADNIL', 'POW', 'CALL', 'SETUPVAL', 'GETUPVAL', 'SELF', 'LE', 'LEN', 'FORLOOP', 'GETGLOBAL', 'VARARG', 'RETURN', 'TESTSET', 'TEST', 'LT', 'TAILCALL', 'CONCAT', 'GETTABLE', 'JMP', 'TFORLOOP', 'LOADK')
# 14646482.0 branch mispredictions
#(monte-carlo n=3000)
