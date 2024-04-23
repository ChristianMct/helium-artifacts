import sys 
import time
import re
import json
import threading
from itertools import product
from churn_sim import NodeSystemSimulation
from sys_runner import DockerNodeSystem
from collections import OrderedDict

# ====== Environment ======
PARTIES_HOST = 'localhost'     # parties should always be run on localhost
CLOUD_HOST = 'localhost'       # hostname or ip of the cloud docker host
EPOCH_TIME = 1                 # time resolution of the failure process simulation
START_WITH_THRESH = False # if true, starts with exactly the threshold number of nodes. Otherwise, starts with the expected number of node for the experiment's failure rate.
EXP_SKIP_THRESH = 0.2 # experiments for which the expected time above threshold is below 20% are skipped

# ====== Experiments parameters ======
RATE_LIMIT = "100mbit" # outbound rate limit for the parties
DELAY = "30ms"         # outbound network delay for the parties
EVAL_COUNT = 10        # number of circuit evaluation performed per experiment

# ====== Experiment Grid ======
N_PARTIES = [7]                         # the number of session nodes
THRESH_VALUES = [3,4]                   # the cryptographic threshold
FAILURE_RATES = range(0, 11, 5)         # the failure rate in fail/min
FAILURE_DURATIONS = [0.333333333333]    # the mean failure duration in min
N_REP = 1                               # number of experiment repetition
SKIP_TO = 0                             # starts from a specific experiment number in the grid


def log(str, end="\n"):
    print(str, file=sys.stderr, end=end, flush=True)


def get_stats(container, print=False):
    stats_json = None
    p = re.compile(r'\d+\.\d+')
    for l in container.logs(stream=True):
        line = l.decode('utf-8')
        if line.startswith("STATS"):
            stats_json = json.loads(line.split()[1])
        if print:
            log("%s | %s" % (container.name, line), end="")
    if stats_json == None:
        raise Exception("Container terminated without outputting stats.")
    return OrderedDict([
        ("TimeSetup", float(stats_json["Time"]["Setup"])/1e9),
        ("SentSetup", float(stats_json["Net"]["Setup"]["DataSent"])/1e6),
        ("RecvSetup", float(stats_json["Net"]["Setup"]["DataRecv"])/1e6),
        ("TimeCompute", float(stats_json["Time"]["Compute"])/1e9),
        ("SentCompute", float(stats_json["Net"]["Compute"]["DataSent"])/1e6),
        ("RecvCompute", float(stats_json["Net"]["Compute"]["DataRecv"])/1e6),
    ])


log("Computing experiments...")
exps_to_run = []
for n_party, thresh, mean_failure_per_min, mean_failure_duration in product(N_PARTIES, THRESH_VALUES, FAILURE_RATES, FAILURE_DURATIONS):
     if thresh == 0:
         thresh = n_party
     sim = NodeSystemSimulation(n_party, mean_failure_per_min, mean_failure_duration, EPOCH_TIME)
     avg_online_count, frac_time_above_thresh = sim.expected_online_nodes(), sim.expected_time_above_threshold(thresh)
     if frac_time_above_thresh < EXP_SKIP_THRESH:
         continue
     exps_to_run.append((n_party, thresh, mean_failure_per_min, mean_failure_duration))
log("%d experiments to run" % (len(exps_to_run)*N_REP))

for i, (exp, rep) in enumerate(product(exps_to_run, range(N_REP))):

    if i+1 < SKIP_TO:
        continue
    
    n_party, thresh, mean_failure_per_min, mean_failure_duration = exp

    log("======= starting experiment N=%d T=%d F=%.2f REP=%d =======" % (n_party, thresh, mean_failure_per_min, rep))

    system = DockerNodeSystem(n_party, thresh, PARTIES_HOST, CLOUD_HOST, RATE_LIMIT, DELAY, EVAL_COUNT)

    churn_sim = NodeSystemSimulation(n_party,
                                    mean_failure_per_min,
                                    mean_failure_duration, 
                                    EPOCH_TIME,
                                    on_failure=system.kill_player,
                                    on_reconnect=system.start_player,
                                    initial_online= thresh if START_WITH_THRESH else None
                                    )
    
    time.sleep(5) # lets the thing clean

    exp_terminated = threading.Event()

    def excepthook(args):
        time.sleep(2)
        if not exp_terminated.is_set():
            raise Exception("Got exception of type %s value %s during experiment" % (args.exc_type, args.exc_value))
    
    threading.excepthook = excepthook

    cloud = system.start_cloud()

    churn_sim.run_simulation()
    
    try:
        stats = get_stats(cloud, print=True)
        exp_desc = OrderedDict(
        [
            ("threshold", thresh),
            ("failure_rate", mean_failure_per_min),
            ("rep", rep),
        ] +
        [item for item in stats.items()] +
        [
            ("failure_duration", mean_failure_duration),
            ("exp", "helium"),
            ("n_party", n_party),
            ("rate_limit", RATE_LIMIT),
            ("delay", DELAY),
            ("theoretical_node_online", churn_sim.expected_online_nodes()),
            ("theoretical_time_above_thresh", churn_sim.expected_time_above_threshold(thresh)),
            ("actual_node_online", churn_sim.online_nodes()),
            ("actual_time_above_thresh", churn_sim.time_above_threshold(thresh)),
        ])

        if churn_sim.failed_fail > 0 or churn_sim.failed_rec > 0:
            print("Warning: churn simulation got %d failed failures and %d failed reconnect" % (churn_sim.failed_fail, churn_sim.failed_rec))

        print(json.dumps(exp_desc), flush=True)
    except Exception as e:
        log(e)
        sys.exit(1)
    finally:
        exp_terminated.set()
        churn_sim.stop()

    time.sleep(2)