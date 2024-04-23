# Helium – Artifacts 

This repository contains the artifacts of the paper _HElium: Scalable MPC among Lightweight Participants and under Churn_. The paper will appear at CCS 2024 and is already available at [https://eprint.iacr.org/2024/194](https://eprint.iacr.org/2024/194).

## List of artifacts
- The HElium repository
    - contains: the code for the HElium system 
    - hosted at [https://github.com/ChristianMct/helium](https://github.com/ChristianMct/helium)
    - mirrored at [https://zenodo.org/doi/10.5281/zenodo.11045945](https://zenodo.org/doi/10.5281/zenodo.11045945)
- The present artifact repository
    - imports HElium at `v0.2.1`
    - contains:
        - an HElium application implementing the paper's experiment
        - an MP-SPDZ application implementing the paper's experiment
        - scripts for building and running both experiments.
    - hosted at [https://github.com/ChristianMct/helium-artifacts](https://github.com/ChristianMct/helium-artifacts)
    - mirrored at [https://zenodo.org/doi/10.5281/zenodo.11046011](https://zenodo.org/doi/10.5281/zenodo.11046011)

**Note:** due to a limitation of the Go building system, the artifact repository cannot import code from Zenodo directly.

## Instructions
This section details the procedure for building and running the HElium experiments.

### Setup
The following software are required on the machine(s) running the experiments:
 - [Docker](https://docs.docker.com/get-docker/)
 - [Python 3.x](https://www.python.org/downloads/)
 - `make`
 - (Optional) [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html) can be used to setup all dependencies ssh-accessible machines automatically.

The following Python packages are also required:
 - `docker`
 - `paramiko`

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
EVAL_COUNT = 100       # number of circuit evaluation performed per experiment

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
EVAL_COUNT = 10        # number of circuit evaluation performed per experiment

# ====== Experiment Grid ======
N_PARTIES = [30]                        # the number of session nodes
THRESH_VALUES = [10, 16, 20]            # the cryptographic threshold
FAILURE_RATES = range(0, 71, 5)         # the failure rate in fail/min
FAILURE_DURATIONS = [0.333333333333]    # the mean failure duration in min
N_REP = 10                              # number of experiment repetition
SKIP_TO = 0
```


