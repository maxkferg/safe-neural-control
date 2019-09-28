"""
Train an agent on SeekerSimEnv

# For a lightweight test
python train.py configs/seeker-test.yaml --dev

# For a GPU driven large test
python train.py configs/seeker-apex-td3.yaml
"""
import io
import ray
import yaml
import numpy as np
import gym
import logging
import argparse
import colored_traceback
from random import choice
from pprint import pprint
from gym.spaces import Discrete, Box
from gym.envs.registration import EnvSpec
from gym.envs.registration import registry
from ray import tune
from ray.tune.schedulers import PopulationBasedTraining
from ray.tune import run_experiments
from ray.tune.registry import register_env
from ray.rllib.models import ModelCatalog
from learning.fusion import FusionModel
from learning.mink import MinkModel
from learning.preprocessing import DictFlatteningPreprocessor
from environment.loaders.geometry import GeometryLoader
from environment.env.base import BaseEnvironment # Env type
from environment.env.multi import MultiEnvironment # Env type
colored_traceback.add_hook()


ENVIRONMENT = "MultiRobot-v0"

# Only show errors and warnings
logging.basicConfig(format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S', level=logging.WARN)


# Load API Config
with open('environment/configs/test.yaml') as cfg:
    api_config = yaml.load(cfg, Loader=yaml.Loader)


def train_env_creator(cfg):
    """
    Create an environment that is linked to the communication platform
    """
    defaults = {
        "debug": True,
        "monitor": True,
        "headless": False,
        "reset_on_target": True
    }
    defaults.update(cfg)
    logging.warn(defaults)
    loader = GeometryLoader(api_config) # Handles HTTP
    base = BaseEnvironment(loader, headless=cfg["headless"])
    return MultiEnvironment(base, verbosity=0, env_config=defaults)


def create_parser():
    parser = argparse.ArgumentParser(
        description='Process some integers.')
    parser.add_argument(
        "config",
        default="configs/seeker-test.yaml",
        type=str,
        help="The configuration file to use for the RL agent.")
    parser.add_argument(
        "--pbt",
        default=False,
        type=bool,
        help="Run population based training.")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use development cluster with local redis server")
    return parser



def run(args):
    ModelCatalog.register_custom_preprocessor("debug_prep", DictFlatteningPreprocessor)
    ModelCatalog.register_custom_model("fusion", FusionModel)
    ModelCatalog.register_custom_model("mink", MinkModel)
    register_env(ENVIRONMENT, lambda cfg: train_env_creator(cfg))

    with open(args.config, 'r') as stream:
        experiments = yaml.load(stream)

    for experiment_name, settings in experiments.items():
        print("Running %s"%experiment_name)
        ray.tune.run(
            settings['run'],
            name=experiment_name,
            stop=settings['stop'],
            config=settings['config'],
            queue_trials=True,
        )


def run_pbt(args):
    pbt_scheduler = PopulationBasedTraining(
        time_attr='time_total_s',
        reward_attr='episode_reward_mean',
        perturbation_interval=4*3600.0,
        hyperparam_mutations={
            "lr": [1e-3, 5e-4, 1e-4, 5e-5, 1e-5],
            "tau": [0.005, 0.001],
            "target_noise": [0.01, 0.1, 0.2],
            "noise_scale": [0.01, 0.1, 0.2],
            "train_batch_size": [2048, 4096, 8192],
            "l2_reg": [1e-5, 1e-6, 1e-7],
        })

    # Prepare the default settings
    with open(args.config, 'r') as stream:
        experiments = yaml.load(stream)

    for experiment, settings in experiments.items():
        settings["env"] = ENVIRONMENT

    run_experiments(experiments, scheduler=pbt_scheduler)



if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    if args.dev:
        ray.init()
    else:
        ray.init("localhost:6379")
    if args.pbt:
        run_pbt(args)
    else:
        run(args)

