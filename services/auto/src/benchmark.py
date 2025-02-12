#!/usr/bin/env python
"""
Test and benchmark environment performances
Uses a simple (no RL) policy to step and render the environment

Example usage:
    python benchmark.py
    python benchmark.py --headless

    python -m cProfile -o results.prof benchmark.py --headless
    snakeviz results.prof
"""

import math
import yaml
import random
import sys, gym, time
import numpy as np
import tkinter
import argparse
import colored_traceback
from PIL import Image, ImageTk
from common import train_env_factory
from environment.core.utils.config import extend_config


tkinter.NoDefaultRoot()

RENDER_WIDTH = 800
RENDER_HEIGHT = 600
MAP_WIDTH = int(195*1.6)
MAP_HEIGHT = int(520*1.6)

RENDER_SIZE = (RENDER_HEIGHT, RENDER_WIDTH)

ENVIRONMENT = "MultiRobot-v0"
DEFAULTS = {
    'headless': False,
    'reset_on_target': True,
    'building_id': '5d984a7c6f1886dacf9c730d'
}




def create_parser(parser_creator=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Benchmark or visualize a reinforcement learning agent ",
        epilog="python benchmark.py --no-render")

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Optionally disable all rendering (default=False).")

    parser.add_argument(
        "--render",
        action="store_true",
        help="Show GUI windows")

    return parser



def config_from_args(args):
    """
    Extract experiment args from the command line args
    These can be used to overrided the args in a yaml file
    """
    config = {}
    if args.headless:
        config["env_config"]["headless"] = True
    if args.render:
        config["env_config"]["headless"] = False
    return config



class BenchmarkWindow():
    """
    Dummy window that does not render the progress
    """
    times = 1
    timestart = time.clock()

    def __init__(self, env):
        self.env = env
        self.action = [0,0]
        self.obs = self.env.reset()

    def start(self):
        while True:
            self.step()

    def step(self):
        action = {}
        for robot, obser in self.obs.items():
            steering = obser["robot_theta"]/math.pi / 4
            throttle = 0
            action[robot] = [steering, throttle]
        self.obs, r, done, info = self.env.step(action)
        self.times += 1
        if self.times%33==0:
            print("%.02f FPS"%(self.times/(time.clock()-self.timestart)))
        if done["__all__"]:
            time_before_reset = time.time()
            env.reset()
            reset_duration = time.time() - time_before_reset
            print("Reset in %.4f seconds"%reset_duration)



class ViewWindow():
    times = 1
    timestart = time.clock()

    def __init__(self, mapw, width, height):
        self.action = [0,0]
        self.width = width
        self.height = height
        self.root = tkinter.Tk()
        self.frame = tkinter.Frame(self.root, width=width, height=height)
        self.frame.pack()
        self.canvas = tkinter.Canvas(self.frame, width=width, height=height)
        self.canvas.place(x=-2, y=-2)
        self.map = mapw
        self.obser = env.reset()

    def start(self):
        self.root.after(0, self.step) # INCREASE THE 0 TO SLOW IT DOWN
        self.root.mainloop()

    def render(self, pixels):
        self.im = Image.fromarray(pixels)
        self.photo = ImageTk.PhotoImage(master=self.root, image=self.im)
        self.canvas.create_image(0, 0, image=self.photo, anchor=tkinter.NW)

    def step(self):
        action = {}
        for robot, obser in self.obser.items():
            steering = obser["target"][0] / math.pi / 4
            throttle = 0.3
            action[robot] = [steering, throttle]
        obs, r, done, info = env.step(action)
        # Render current state
        self.render(env.render(mode="rgb_array", width=self.width, height=self.height))
        #self.map.render(obs["map"])
        self.times += 1
        if self.times%33==0:
            print("%.02f FPS"%(self.times/(time.clock()-self.timestart)))
        self.root.after(500, self.step)
        #time.sleep(0.3)
        if done['__all__']:
            print("--- Resetting ---")
            env.reset()



class MapWindow():
    times = 1
    timestart = time.clock()

    def __init__(self, width, height):
        self.action = [0,0]
        self.width = width
        self.height = height
        self.root = tkinter.Tk()
        self.frame = tkinter.Frame(self.root, width=width, height=height)
        self.frame.pack()
        self.canvas = tkinter.Canvas(self.frame, width=width, height=height)
        self.canvas.place(x=-2, y=-2)

    def start(self):
        self.root.after(0, self.step) # INCREASE THE 0 TO SLOW IT DOWN
        self.root.mainloop()

    def render(self, pixels):
        pixels = np.flip(pixels, axis=0)
        self.im = Image.fromarray(pixels)
        self.photo = ImageTk.PhotoImage(master=self.root, image=self.im)
        self.canvas.create_image(0, 0, image=self.photo, anchor=tkinter.NW)


if __name__=="__main__":
    parser = create_parser()
    args = parser.parse_args()
    cfg = extend_config(DEFAULTS, config_from_args(args))
    env = train_env_factory()(cfg)
    view = BenchmarkWindow(env)
    # Not working at the moment
    #else:
    #    mapw = MapWindow(MAP_WIDTH, MAP_HEIGHT)
    #    view = ViewWindow(mapw, RENDER_WIDTH, RENDER_HEIGHT)
    view.start()
