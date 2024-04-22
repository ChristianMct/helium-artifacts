import threading
import random
import time
import sys
from math import comb
import pandas as pd
#import matplotlib.pyplot as plt 

def log(str, end="\n"):
    print(str, file=sys.stderr, end=end, flush=True)

class NodeSystemSimulation:
    def __init__(self, N, system_failure_rate, avg_reconnection_time, epoch_duration=1, 
                 on_failure=None, on_reconnect=None, initial_online=None):
        self.N = N
        self.system_failure_rate = system_failure_rate
        self.avg_reconnection_time_sec = avg_reconnection_time*60
        self.epoch_duration = epoch_duration
        self.lambda_r = 1 / (avg_reconnection_time * 60)
        self.lambda_f = (-system_failure_rate/60*self.lambda_r)/((system_failure_rate / 60) - (N-1) *self.lambda_r)
        

        # Setting up initial online nodes
        if initial_online is None:
            expected_online = self.expected_online_nodes()
            initial_online = min(N, max(0, int(expected_online)))
        self.nodes = [True] + [i < initial_online for i in range(1, N)] # node-0 and (initial_online - 1) are up

        self.on_failure = on_failure if on_failure is not None else self.default_failure_action
        self.on_reconnect = on_reconnect if on_reconnect is not None else self.default_reconnect_action
        self.simulation_thread = None
        self.stop_signal = threading.Event()

        self.stats_online = []
        self.stats_fail = []
        self.stats_rec = []
        self.failed_fail = 0
        self.failed_rec = 0

    def default_failure_action(self, node_id):
        None
        #print(f"Node {node_id} failed.")

    def default_reconnect_action(self, node_id):
        None
        #print(f"Node {node_id} reconnected.")

    def run_epoch(self):
        nfail = 0
        nrec = 0
        for i in range(1, self.N):
            if self.stop_signal.is_set():
                break
            if self.nodes[i]:  # Node is online
                if random.random() < self.lambda_f * self.epoch_duration:
                    try:
                        log("failing node-%d, online=%d/%d" % (i, sum(self.nodes), len(self.nodes)))
                        self.on_failure(i)
                        self.nodes[i] = False
                        nfail += 1
                    except:
                        self.failed_fail += 1

            else:  # Node is offline
                if random.random() < self.lambda_r * self.epoch_duration:
                    try:
                        log("re-connected node-%d, online=%d/%d" % (i, sum(self.nodes), len(self.nodes)))
                        self.on_reconnect(i)
                        self.nodes[i] = True
                        nrec+=1
                    except:
                        self.failed_rec += 1
        if self.stop_signal.is_set():
            return 0, 0 # failures to fail/reconnect after termination are normal (node have exited normally) 
        return nfail, nrec

    def simulation_loop(self, live):
        while not self.stop_signal.is_set():
            epoch_start_time = time.time()
            nfail, nrec = self.run_epoch()
            self.stats_fail.append(nfail)
            self.stats_rec.append(nrec)
            self.stats_online.append(sum(self.nodes))
            epoch_time = time.time() - epoch_start_time
            if epoch_time < self.epoch_duration:
                time.sleep(self.epoch_duration - epoch_time) if live else None
            else:
                log("epoch time %.2f longer than epoch duration %.2f" % (epoch_time, self.epoch_duration) )

    def run_simulation(self, total_epochs=None, live=True):
        
        node_to_start = [i for i, online in enumerate(self.nodes) if online]
        log("starting %d nodes: %s..." % (len(node_to_start), node_to_start))
        start_threads = [threading.Thread(target=self.on_reconnect, args=(i,)) for i in node_to_start]
        [thr.start() for thr in start_threads]
        [thr.join() for thr in start_threads]
        
        if total_epochs is None:
            self.simulation_thread = threading.Thread(target=self.simulation_loop, args=(live,))
            self.simulation_thread.start()
        else:
            for _ in range(total_epochs):
                nfail, nrec = self.run_epoch()
                self.stats_fail.append(nfail)
                self.stats_rec.append(nrec)
                self.stats_online.append(sum(self.nodes))
                time.sleep(self.epoch_duration) if live else None

    def stop(self):
        if self.simulation_thread and self.simulation_thread.is_alive():
            self.stop_signal.set()
            self.simulation_thread.join()

    def expected_online_nodes(self):
        # Expected number of online nodes in stable state
        return 1 + (self.N-1) * (1 / (self.lambda_f * self.avg_reconnection_time_sec + 1))

    def expected_time_above_threshold(self, T):
        # Expected fraction of time with at least T online nodes
        p_online = 1 / (self.lambda_f * self.avg_reconnection_time_sec + 1)
        return sum(comb(self.N-1, k) * p_online**k * (1 - p_online)**((self.N - 1) - k) for k in range(T-1, (self.N -1) + 1))
    
    def online_nodes(self):
        return sum(self.stats_online)/len(self.stats_online)
    
    def time_above_threshold(self, T):
        return sum([1 for n_online in self.stats_online if n_online >= T])/len(self.stats_online)
    
    def avg_fail_per_epoch(self):
        return sum(self.stats_fail)/len(self.stats_fail)

    def avg_rec_per_epoch(self):
        return sum(self.stats_rec)/len(self.stats_rec)

    def fail_per_min(self):
        return (self.avg_fail_per_epoch()/self.epoch_duration)*60
    
    def rec_per_min(self):
        return (self.avg_rec_per_epoch()/self.epoch_duration)*60

if __name__ == '__main__':
    # Example usage

    T=10

    simulation = NodeSystemSimulation(N=30, epoch_duration=0.5, system_failure_rate=0, avg_reconnection_time=99999, initial_online=T)
    print("Expected online = %.2f above T = %.2f fail/min = %.2f" % (
        simulation.expected_online_nodes(),
        simulation.expected_time_above_threshold(T),
        simulation.lambda_f*(simulation.expected_online_nodes()-1)*60,
        ))
    simulation.run_simulation(total_epochs=1000000, live=False)  # Runs until stop() is called
    # ... After some time or condition
    #time.sleep(10)
    #simulation.stop()
    print("Actual online = %.2f above T = %.2f  fail/epoch = %.5f fail/min = %.5f rec/min = %.2f" % (
        simulation.online_nodes(), 
        simulation.time_above_threshold(T),
        simulation.avg_fail_per_epoch(),
        simulation.fail_per_min(),
        simulation.rec_per_min()
        ))

    # frs =range(10, 400, 5)
    # ts = dict()
    # for t in [10, 16, 20]:
    #     avg_on = []
    #     frac_t = []
    #     for fr in frs:
    #         sim = NodeSystemSimulation(N=30, epoch_duration=.5, system_failure_rate=fr, avg_reconnection_time=0.3333333)
    #         avg_on.append(sim.expected_online_nodes())
    #         frac_t.append(sim.expected_time_above_threshold(t))
    #     ts[t] = avg_on

    # df = pd.DataFrame(ts, index=frs)
    # plot = df.plot()
    # plt.show()