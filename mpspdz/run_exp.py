import docker
import sys
from itertools import product
import re
import time

# ====== Experiments parameters ======
EXP_CONTAINER_LABEL = "helium-exp"
RATE_LIMIT = "100mbit"
DELAY = "30ms"
PROGRAM = "matmult"

# ====== Experiment Grid ======
MACHINES = ["semi", "soho", "temi", "hemi"]
N_PARTIES = range(2, 4)
N_REP = 1

def log(str, end="\n"):
    print(str, file=sys.stderr, end=end)

def get_all():
    return client.containers.list(filters={"label": EXP_CONTAINER_LABEL}, all=True, ignore_removed=True)

def stop_all():
    for container in get_all():
        container.kill()

def clean_all():
    for container in get_all():
        try:
            container.remove(force=True)
        except:
            continue

client = docker.from_env()

p = re.compile(r'\d+\.\d+')

def start_player(i, n_party, exp):
    container_name = "player-%d" % i
    cmd = "party.x %d -N %d %s -pn 12669 -h player-0 -v -OF ." % (i, n_party, PROGRAM)
    caps = ["NET_ADMIN"]
    net = "expnet"
    env = {"RATE_LIMIT": RATE_LIMIT, "DELAY": DELAY}
    return client.containers.run('exp:%s' % exp,
                                            name=container_name,
                                            hostname=container_name,
                                            command=cmd,
                                            cap_add=caps,
                                            network=net,
                                            environment=env,
                                            remove=True,
                                            labels=[EXP_CONTAINER_LABEL],
                                            detach=True)
    

nets = [net.name for net in client.networks.list(names=["expnet"])]
if "expnet" not in nets:
    log("creating network")
    client.networks.create("expnet", driver="bridge")


clean_all()

for exp, n_party, rep in product(MACHINES, N_PARTIES, range(N_REP)):
    log("======= starting experiment %s with %s parties =======" % (exp, n_party))
    for i in reversed(range(n_party)):
        c = start_player(i, n_party, exp)
        if i == 0:
            floats = []
            for l in c.logs(stream=True):
                line = l.decode('utf-8')
                if line.startswith("Spent"):
                    floats = [float(i) for i in p.findall(line)]
                log("player-%d | %s" % (i, line), end="")
            res = {
                    "exp": exp, 
                    "rep": rep,
                    "n_party": n_party,
                    "rate_limit": RATE_LIMIT,
                    "delay": DELAY,
                    "TimeOnline": floats[0],
                    "SentOnline": floats[1],
                    "TimeOffline": floats[2], 
                    "SentOffline": floats[3]
            }
            print(res, flush=True)
            clean_all()
            time.sleep(5) # leaves some time for docker to cleanup the containers
