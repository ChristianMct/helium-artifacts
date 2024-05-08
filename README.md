# Helium – Artifacts 

This repository contains the artifacts of the paper _Helium: Scalable MPC among Lightweight Participants and under Churn_. The paper will appear at CCS 2024 and is already available at [https://eprint.iacr.org/2024/194](https://eprint.iacr.org/2024/194).

## List of artifacts
- The Helium repository
    - contains: the code for the Helium system 
    - hosted at [https://github.com/ChristianMct/helium](https://github.com/ChristianMct/helium)
    - mirrored at [https://zenodo.org/doi/10.5281/zenodo.11045945](https://zenodo.org/doi/10.5281/zenodo.11045945)
    - is **main artifact** and constitutes its reusable, more documented part
- The present artifact repository
    - imports the Helium repository at `v0.2.1`
    - contains:
        - an Helium application implementing the paper's experiment
        - an MP-SPDZ application implementing the paper's baseline
        - scripts for building and running both experiments.
    - hosted at [https://github.com/ChristianMct/helium-artifacts](https://github.com/ChristianMct/helium-artifacts)
    - mirrored at [https://zenodo.org/doi/10.5281/zenodo.11046011](https://zenodo.org/doi/10.5281/zenodo.11046011)
    - is a **secondary artifact** which scope is solely to reproduce the paper's experiments

## Instructions
This section details the procedure for building and running the Helium experiments (i.e., the Helium part of Experiment I
and the whole Experiment II).

### Setup
The following software are required on the machine(s) running the experiments (see below for an automated way of setting up the machines). 
The version numbers are those used for the paper's results, but are only indicative.
 - [Docker](https://docs.docker.com/get-docker/), version 26.1.1
 - [Python 3](https://www.python.org/downloads/), version 3.10.12
 - `make`, version 4.3

The following Python packages are also required:
 - `docker`, version 7.0.0
 - `paramiko`, version 3.4.0

 [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html) can be used to setup all the above dependencies on ssh-accessible machines (the following instructions include the related command).

### Running locally
In this first part, we cover the steps to run a small scale test experiment, to demonstrate the process.
We assume it is performed on a local machine for which the requirement are already setup. If you are planning 
to work on a server directly, please see the next part as it includes an automated setup from SSH.

1. Clone the artifact repository: `git clone https://github.com/ChristianMct/helium-artifacts && cd helium-artifacts`
2. Build the experiment Docker image: `make helium`
4. Run the experiment: `python3 helium/exp_runner/main.py >> results`

This last command runs the experiments for a grid of parameters and stores the results in `./result`. 
By default, the experiment and grid parameters represent a small set of experiments, for local test purposes.
To reproduce the results of the paper, larger scale experiments have to be run, which require two servers.

### Running on two servers
For this part, we assume that the steps above have been performed on a local machine that has publickey SSH access to two servers 
with host names `<host1>` and `<host2>`, **and that** `<host1>` **has publickey SSH access to** `<host2>`. In the steps below `<host1>` will drive 
the experiment and run the session nodes, while `<host2>` will run the helper "cloud". 

1. Setup the servers with Ansible: `ansible-playbook -i <host1>,<host2> conf/ansible/setup_server.pb.yml`
2. SSH into `<host1>` and `cd helium-artifacts`
3. Open the experiment runner script at `helium/exp_runner/main.py`
4. Change the docker host name for the cloud: `CLOUD_HOST = 'localhost'` => `CLOUD_HOST = '<host2>'`
5. Run the experiment: `python3 exp_runner/main.py >> results`

### Controlling the experiment parameters and grid
To reproduce the paper experiments, we further modify the runner script parameters. The snippets below represent the actual experiment grids
of the paper. Note that fully running these grids might take a significant time. Although this should be unfrequent, might also be some bugs 
left which prevents an experiment from completing. The `SKIP_TO` variable enables restarting from a specific point in the grid.

#### Experiment I
```python
# ====== Experiments parameters ======
RATE_LIMIT = "100mbit" # outbound rate limit for the parties
DELAY = "30ms"         # outbound network delay for the parties
EVAL_COUNT = 10       # number of circuit evaluation performed per experiment

# ====== Experiment Grid ======
N_PARTIES = range(2, 11, 2)             # the number of session nodes
THRESH_VALUES = [0]                     # the cryptographic threshold
FAILURE_RATES = [0]                     # the failure rate in fail/min
FAILURE_DURATIONS = [0.333333333333]    # the mean failure duration in min
N_REP = 10                              # number of experiment repetition
SKIP_TO = 0
```

**Note**: for this experiment, we compute the per-party network cost as the cloud network cost divided by the number of parties (since the 
protocol is fully symmetric).

#### Experiment II
```python
# ====== Experiments parameters ======
RATE_LIMIT = "100mbit" # outbound rate limit for the parties
DELAY = "30ms"         # outbound network delay for the parties
EVAL_COUNT = 100        # number of circuit evaluation performed per experiment

# ====== Experiment Grid ======
N_PARTIES = [30]                        # the number of session nodes
THRESH_VALUES = [10, 16, 20]            # the cryptographic threshold
FAILURE_RATES = range(0, 71, 5)         # the failure rate in fail/min
FAILURE_DURATIONS = [0.333333333333]    # the mean failure duration in min
N_REP = 10                              # number of experiment repetition
SKIP_TO = 0
```

### Result format
The result of a single experiment is a JSON string. Here is a description of its fields:
- `n_party`: the number of parties ($N$ in the paper)
- `threshold`: the cryptographic threshold ($T$ in the paper)
- `failure_rate`: the system-wide failure rate in failure/min ($\Lambda_f$ in the paper)
- `failure_duration`: the expected failure duration in min ($\lambda_r^{-1}$ in the paper)
- `rep`: the experiment repetition identifier
- `rate_limit`: the session nodes' network rate limit (outgoing only)
- `delay`: the session nodes' network delay (outgoing only)
- `TimeSetup`: wall time in Seconds between the start and the end of the setup phase, measured at the helper. The setup phase starts upon triggering the first public-key generation protocol and ends when the last required public-key is generated.
- `SentSetup`: setup-related outgoing network traffic volume in Megabytes at the helper. 
- `RecvSetup`: setup-related incoming network traffic volume in Megabytes at the helper.
- `TimeCompute`: wall time in Seconds between the start and end of the compute phase. The compute phase starts upon triggering the first circuit execution and ends when all circuits (controlled by `EVAL_COUNT` in the python script) have been evaluated.
- `SentCompute`: compute-related outgoing network traffic volume in Megabyte at the helper.
- `RecvCompute`: compute related incoming network traffic volume in Megabyte at the helper.
- `theoretical_node_online`: expected number of online node at equilibrium ($E[N_{online}]$ in the paper.) 
- `theoretical_time_above_thresh`: expected fraction of time for which at least T nodes are online at equilibrium ($Pr[N_{online} \geq T]$ in the paper) 
- `actual_node_online`: empirical average number of online node during the experiment.
- `actual_time_above_thresh`: empirical fraction of time for which at least $T$ nodes were online during the experiment.

The experiment runner executes all experiment in the grid, outputting each experiment result on a new line.

### Further configuration of Helium
The configuration of the Helium nodes in the experiments can be found in the `genConfigForNode` function of the `helium/app/main.go` file.
The current configuration matches the one used for the paper's experiment, and it has the following performance-related characteristics:
- it uses FHE parameters with a polynomial degree of $2^12$ and a coefficient modulus of 109 bits.
- it limits to 3 the number concurrently running protocols per *session node* (`MaxProtoPerNode` and `MaxParticipation`), and to 32 the number of concurrently running protocols at the helper (`MaxAggregation`).
- it limits to 10 the number of concurrently running circuits (`MaxCircuitEvaluation`).

## Reproducing the MP-SPDZ baseline results
This section is aimed at reproducing the MP-SPDZ baseline results. Note that this part is time consuming and subject to more randomness that
is out of our control. The build part takes ~15 minutes on our machine. The run part depends on the grid and can be approximated from the 
result in our paper. The default experiment runs all baseline for 2 and 3 parties without repetition so it should take around an hour to complete.

1. Build the mpspdz images: `make mpspdz`
2. (Optional) if the last build fail, `rm -rf mpspdz/deps/MP-SPDZ/deps/SimplestOT_C` and start from 1.
3. Run the experiments: `python3 mpspdz/run_exp.py >> mpspdz_results`

The snippet provides the experiment grid used in the paper:
```python
# ====== Experiment Grid ======
MACHINES = ["semi", "soho", "temi", "hemi"]
N_PARTIES = range(2, 11)
N_REP = 10
```
**Note**: we used `N_REP=1` to match the experiment grid in of the Helium experiment. However, this is probably an overkill because of the 
small variance and the large gap between Helium and its baseline. `N_REP=1` is probably good enough for reproducing the results.
