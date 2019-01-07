import numpy as np
import math
import os
import pygame
from pygame.locals import *
from configparser import ConfigParser

from gym import core, spaces
from gym.utils import seeding

__author__ = "Xuxi Yang <xuxiyang@iastate.edu>"


class SingleAircraftEnv(core.Env):
    """
    This is the airspace simulator where we can control single aircraft (yellow aircraft)
    to reach the goal position (green star) while avoiding conflicts with other intruder aircraft (red aircraft).
    **STATE:**
    The state consists all the information needed for the ownship to choose an optimal action:
    position, velocity of intruder aircraft
    position, velocity, speed, heading angle, bank angle
    position of the goal
    In the beginning of each episode, the ownship starts in the bottom right corner of the map and the heading angle is
    pointing directly to the center of the map.
    **ACTIONS:**
    The action is either applying +1, 0 or -1 for the change of bank angle and +1, 0, -1 for the change of acceleration
    """

    def __init__(self, config_path):
        self.config_path = config_path
        self.load_config()
        state_dimension = self.intruder_size * 4 + 9
        high = np.ones(shape=[1, state_dimension]) * 100000
        low = -high
        self.observation_space = spaces.Box(low=low, high=high, dtype=np.float32)
        self.position_range = spaces.Box(
            low=np.array([0, 0]),
            high=np.array([self.window_width, self.window_height]),
            dtype=np.float32)
        self.action_space = spaces.Tuple((spaces.Discrete(3), spaces.Discrete(3)))
        self.state = None
        self.seed(2)

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def reset(self):
        # ownship = recordtype('ownship', ['position', 'velocity', 'speed', 'heading', 'bank'])
        # intruder = recordtype('intruder', ['id', 'position', 'velocity'])
        # goal = recordtype('goal', ['position'])

        self.drone = ownship(
            position=(self.window_width - 50, self.window_height - 50),
            speed=self.min_speed,
            heading=45,
            config_path=self.config_path
        )

        self.intruder_list = []
        for _ in range(self.intruder_size):
            intruder = aircraft(
                position=self.random_pos(),
                speed=self.random_speed(),
                heading=self.random_heading(),
            )
            while dist(self.drone, intruder) < self.initial_min_dist:
                intruder.position = self.random_pos()

            self.intruder_list.append(intruder)

        self.goal = goal(position=self.random_pos())
        return self._get_ob()

    def load_config(self):
        parser = ConfigParser(os.environ)
        parser.read(self.config_path)
        # input dim
        self.window_width = parser.getint('default', 'width')
        self.window_height = parser.getint('default', 'height')
        self.intruder_size = parser.getint('default', 'intruder_size')
        self.EPISODES = parser.getint('default', 'EPISODES')
        self.G = parser.getfloat('default', 'G')
        self.tick = parser.getint('default', 'tick')
        self.scale = parser.getint('default', 'SCALE')
        self.minimum_separation = parser.getint('default', 'minimum_separation')/self.scale
        self.NMAC_dist = parser.getint('default', 'NMAC_dist')/self.scale
        self.horizon_dist = parser.getint('default', 'horizon_dist')/self.scale
        self.initial_min_dist = parser.getint('default', 'initial_min_dist')/self.scale
        self.goal_radius = parser.getint('default', 'goal_radius')/self.scale
        self.min_speed = parser.getint('aircraft_model', 'min_speed')/self.scale
        self.max_speed = parser.getint('aircraft_model', 'max_speed')/self.scale

    def _get_ob(self):
        s = []
        for i in range(self.intruder_size):
            s.append(self.intruder_list[i].position[0])
            s.append(self.intruder_list[i].position[1])
            s.append(self.intruder_list[i].velocity[0])
            s.append(self.intruder_list[i].velocity[1])
        for i in range(1):
            # (x, y, vx, vy, speed, heading, bank)
            s.append(self.drone.position[0])
            s.append(self.drone.position[1])
            s.append(self.drone.velocity[0])
            s.append(self.drone.velocity[1])
            s.append(self.drone.speed)
            s.append(self.drone.heading)
            s.append(self.drone.bank)
        s.append(self.goal.position[0])
        s.append(self.goal.position[1])

        return np.array(s)

    def step(self, a):
        # intruder aircraft
        for id in range(self.intruder_size):
            intruder = self.intruder_list[id]
            intruder.position += intruder.velocity
            if not self.position_range.contains(intruder.position):
                self.intruder_list[id] = self.reset_intruder()

        # ownship aircraft
        self.drone.step(a)

        reward, terminal, info = self._terminal_reward()

        return self._get_ob(), reward, terminal, info

    def _terminal_reward(self):
        if not self.position_range.contains(self.drone.position):
            return 0, True, 'wall'
        for intruder in self.intruder_list:
            if dist(self.drone, intruder) < self.minimum_separation:
                return 0, True, 'conflict'
        if dist(self.drone, self.goal) < self.goal_radius:
            return 1, True, 'goal'
        return 0, False, ''

    def render(self, mode='human'):
        pygame.init()
        screen = pygame.display.set_mode(self.window_width, self.window_height)
        clock = pygame.time.Clock()
        gameIcon = pygame.image.load('image/intruder.png')
        pygame.display.set_icon(gameIcon)
        pygame.display.set_caption('Free Flight Airspace Simulator', 'Spine Runtime')
        pass

    def reset_intruder(self):
        intruder = aircraft(
            position=self.random_pos(),
            speed=self.random_speed(),
            heading=self.random_heading(),
        )
        while dist(self.drone, intruder) < self.initial_min_dist:
            intruder.position = self.random_pos()

        return intruder

    def random_pos(self):
        return np.random.uniform(
            low=np.array([0, 0]),
            high=np.array([self.window_width, self.window_height])
        )

    def random_speed(self):
        return np.random.uniform(low=self.min_speed, high=self.max_speed)

    def random_heading(self):
        return np.random.uniform(low=0, high=360)

    def build_observation_space(self):
        s = spaces.Dict({
            'own_x': spaces.Box(low=0, high=self.window_width, dtype=np.float32),
            'own_y': spaces.Box(low=0, high=self.window_height, dtype=np.float32),
            'pos_x': spaces.Box(low=0, high=self.window_width, dtype=np.float32),
            'pos_y': spaces.Box(low=0, high=self.window_height, dtype=np.float32),
            'heading': spaces.Box(low=0, high=360, dtype=np.float32),
            'speed': spaces.Box(low=self.min_speed, high=self.max_speed, dtype=np.float32),
        })

        return s


class goal:
    def __init__(self, position):
        self.position = position


class aircraft:
    def __init__(self, position, speed, heading):
        self.position = np.array(position, dtype=np.float32)
        self.speed = speed
        self.heading = heading  # degree
        self.rad = math.radians(self.heading)
        vx = -self.speed * math.sin(self.rad)
        vy = -self.speed * math.cos(self.rad)
        self.velocity = np.array([vx, vy], dtype=np.float32)


class ownship(aircraft):
    def __init__(self, position, speed, heading, config_path):
        aircraft.__init__(self, position, speed, heading)
        self.bank = 0  # degree
        self.delta_heading = 0

        self.load_config(config_path)

    def load_config(self, config_path):
        parser = ConfigParser(os.environ)
        parser.read(config_path)

        self.G = parser.getfloat('default', 'G')
        self.scale = parser.getint('default', 'scale')
        self.min_speed = parser.getint('aircraft_model', 'min_speed')/self.scale
        self.max_speed = parser.getint('aircraft_model', 'max_speed')/self.scale
        self.d_speed = parser.getint('aircraft_model', 'd_speed')/self.scale
        self.speed_sigma = parser.getint('uncertainty', 'speed_sigma')/self.scale
        self.position_sigma = parser.getint('uncertainty', 'position_sigma')/self.scale

        self.min_bank = parser.getint('aircraft_model', 'min_bank')
        self.max_bank = parser.getint('aircraft_model', 'max_bank')
        self.d_bank = parser.getint('aircraft_model', 'd_bank')
        self.bank_sigma = parser.getint('uncertainty', 'bank_sigma')

    def step(self, a):
        self.speed += self.d_speed * (a[1] - 1)
        self.speed = max(self.min_speed, min(self.speed, self.max_speed))  # project to range
        self.speed += np.random.normal(0, self.speed_sigma)
        self.bank += self.d_bank * (a[0] - 1)
        self.bank = max(self.min_bank, min(self.bank, self.max_bank))  # clip
        self.bank += np.random.normal(0, self.bank_sigma)
        self.delta_heading = self.bank_to_heading(self.bank, self.speed)
        self.heading += self.delta_heading
        self.heading %= 360
        self.rad = math.radians(self.heading)
        vx = -self.speed * math.sin(self.rad)
        vy = -self.speed * math.cos(self.rad)
        self.velocity = np.array([vx, vy])

        self.position += self.velocity

    def bank_to_heading(self, bank, speed):
        direction = self.G * math.tan(math.radians(bank)) / (self.scale * float(speed))

        return math.degrees(direction)


def dist(object1, object2):
    return np.linalg.norm(object1.position - object2.position)
