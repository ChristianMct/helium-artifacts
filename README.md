# Helium – Experiments 

This repository implements the experiments for the Helium system.

It consists in several docker images and the script to run them.

The Helium code is available in anonymized form in the `helium/deps/helium` directory.

## Experiment

The experiment is a 512x512 matrix-vector multiplication mod 65537 circuit. The time and network cost is measured at party 0.

**Helium** 
We implement an Helium application for this circuit at in the `helium/app` folder.

**MP-SPDZ**
We benchmark all semi-honest protocols for the dishonest majority in the framework.
They all use the same online phase with Beaver triplets, but use different offline phases:
- `semi`: OT-based
- `soho`: HbC HighGear.
- `temi`: LWE-based adaptation of Cramer et al. 2000
- `hemi`: HbC LowGear. 

## Building the experiments

The experiments can be built with a Makefile. Running:
````
make all
````
builds all the experiments. Note that the MP-SPDZ images can take a significant time to build. To build the Helium experiments only, use
````
make -C helium 
````

## Running the expermients

**Experiment I (MP-SPDZ part)**
A python script enables running the experiments. The experiment parameters and the grid of experiment to run is controlled from within the script.
Running:
````
cd mpspdz
python3 run_exp.py > exp_result.json
````
runs all the experiments in the grid, and write the results to the exp_result.json file.

**Experiment I (Helium part) and II**
A python script enables running the experiments. The experiment parameters and the grid of experiment to run is controlled from within the script.
Running:
````
cd helium
python3 exp_runner/main.py > exp_result.json
````
runs all the experiments in the grid, and write the results to the exp_result.json file.

