# Safe Neural Control

This repository contains:
1) A building simulator for simulating the movement of robots in various building scenarios. [[ui](../../ui)] [[api server](../../api)]

2) A web-based editor for creating and viewing navigation scenarios. [[source](../../ui)]

3) An autonomous mobile robot control algorithm that uses pointcloud data for control.

4) Benchmark navigation tasks. [[Gym environments](src/environment)]

![Digital Building Model Demo](https://raw.githubusercontent.com/maxkferg/dbm/master/src/assets/results/readme.gif)


## Safe Neural Control Service

In training mode:
- The cluster pulls building geometry from a training building
- The service simulates the environment and learns a good navigation policy

In rollout mode:
- The service pulls building geometry from a training building
- The service subscribes to building geometry and robot position, keeping the model current
- The service writes trajectories and control actions to the cluster, for every robot
- A Kafka-ROS connector interprets the messages and (possibly) sends them the robot

In visualization mode:
- The service pulls building geometry from a training building
- The service subscribes to building geometry and robot position, keeping the model current
- The service writes trajectories and Q-values to the server


# Quick Start

Training
```sh
ray attach --tmux cluster.yaml
python train.py configs/seeker-sacq-test.yaml --dev
```

Testing
```sh
export API=http://api.digitalpoints.io/graphql
export KAFKA=http://kafka
python rollout.py --run SACQ --env MultiRobot-v0
```


# Docker Support

Building the docker image
```
export TAG=latest
docker build -t digitalpoints/trainer:$TAG .

export TAG=gpu
docker build -f Dockerfile-gpu -t digitalpoints/trainer:$TAG .
```
```

Starting the training process:
```
# Development
docker run -it digitalpoints/trainer:latest \
	python train.py configs/seeker-test-vector.yaml --dev

# Large-scale
docker run -it digitalpoints/trainer:$TAG \
	python train.py configs/seeker-apex-td3.yaml
```

Deploying
```
docker push digitalpoints/trainer:$TAG
```



# Setup
The digital building model has realistic physics, implimented using PyBullet. A great tutorial for
PyBullet can be found here: https://docs.google.com/document/d/10sXEhzFRSnvFcl3XxNGhnD4N2SedqwdAvK3dsihxVUA/edit.
The conda package manager is used to manage dependencies. To install the required packages:

```sh
cd sim
conda env create -f sim.yml
```

# Training
There are two types of agenta which can be trained to navigate the enviroment:
* Seeker - An agent that uses a Lidar sensor to avoid walls
* Mapper - An agent that uses a stack of 2D maps to navigate in the world

In general, `Seeker` is easier to train but `Mapper` performs better. 

Training requires a large number of samples and should be conducted on a Ray cluster.
```sh
ray attach --tmux cluster.yaml
python train.py configs/mapper-apex-td3.yaml
```

### Training locally
Is is possible to run the training process locally:
```sh
python train.py configs/mapper-test.yaml --dev=True
```

# Environment
The environment can be tested using a very simple policy (no RL) using the `benchmark.py` file.
```
python benchmark.py             # Render environment
python benchmark.py --no-render # Benchmark environment performance
```

# Evaluation
A trained agent can be evaluated using the `rollout.py` file.
```
python rollout.py --run APEX_DDPG --env MultiRobot-v0 --steps 1000
python rollout.py --run APEX_DDPG --env MultiRobot-v0 --steps 10000 --checkpoint=/path/to/checkpoint
python rollout.py --run APEX_DDPG --env MultiRobot-v0 --steps 10000 --no-render
```

# Prerequsites:
Some parts of the codebase rely on the latest (`0.7.0`) release of ray. Installing ray with `pip install ray` should work. However, it is better to install the dev version:

```sh
# Linux
pip install -U https://s3-us-west-2.amazonaws.com/ray-wheels/latest/ray-0.7.0.dev0-cp36-cp36m-manylinux1_x86_64.whl

# Mac OSX
pip install -U https://s3-us-west-2.amazonaws.com/ray-wheels/latest/ray-0.7.0.dev0-cp36-cp36m-macosx_10_6_intel.whl
```

If you have problems with ROS, remove any references to python2.7 from PATH and PYTHONPATH


Instructions on setting up tensorflow on Google cloud are available here:
https://medium.com/google-cloud/setting-up-tensorflow-gpu-on-google-cloud-instance-with-ubuntu-16-04-53cb6749b527

# Clusters
```sh
# Create or update the cluster
$ ray up configs/cluster.yaml

# Reconfigure autoscaling behavior without interrupting running jobs
$ ray up configs/cluster.yaml --max-workers=N --no-restart

# Teardown the cluster
$ ray down configs/cluster.yaml
```

# License
MIT