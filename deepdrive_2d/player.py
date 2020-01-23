import math
from math import cos, sin, pi
import os
import sys

import numpy as np

from loguru import logger as log

import arcade
import arcade.color as color
from deepdrive_2d.constants import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_MARGIN, \
    MAP_WIDTH_PX, MAP_HEIGHT_PX, PLAYER_TURN_RADIANS_PER_KEYSTROKE, \
    SCREEN_TITLE, \
    CHARACTER_SCALING, MAX_PIXELS_PER_SEC_SQ, TESLA_LENGTH, VOYAGE_VAN_LENGTH, \
    USE_VOYAGE, VEHICLE_PNG, MAX_METERS_PER_SEC_SQ, MAP_IMAGE
# Constants
from deepdrive_2d.envs.env import Deepdrive2DEnv
from deepdrive_2d.map_gen import get_intersection

DRAW_COLLISION_BOXES = True
DRAW_WAYPOINT_VECTORS = False
DRAW_INTERSECTION = True

# TODO: Calculate rectangle points and confirm corners are at same location in
#   arcade.


# noinspection PyAbstractClass
class Deepdrive2DPlayer(arcade.Window):
    """Allows playing the env as a human"""
    def __init__(self, add_rotational_friction=False,
                 add_longitudinal_friction=False, env=None,
                 fps=60, static_obstacle=False, one_waypoint=False):

        # Call the parent class and set up the window
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE,
                         update_rate=1/fps)
        self.add_rotational_friction = add_rotational_friction
        self.add_longitudinal_friction = add_longitudinal_friction
        self.fps = fps

        arcade.set_background_color(arcade.csscolor.CORNFLOWER_BLUE)
        self.player_sprite: arcade.Sprite = None
        self.player_list = None
        self.wall_list = None
        self.physics_engine = None
        self.human_controlled = False if env else True
        self.env: Deepdrive2DEnv = env
        self.steer = 0
        self.accel = 0
        self.brake = False
        self.map = None
        self.angle = None
        self.background = None
        self.max_accel = None
        self.px_per_m = None
        self.static_obstacle = (static_obstacle or
                                self.env.unwrapped.add_static_obstacle)
        self.one_waypoint = one_waypoint

    def setup(self):
        """ Set up the game here. Call this function to restart the game. """
        self.player_list = arcade.SpriteList()
        self.player_sprite = arcade.Sprite(VEHICLE_PNG,
                                           CHARACTER_SCALING)

        vehicle_length_pixels = self.player_sprite.height
        vehicle_width_pixels = self.player_sprite.width
        if USE_VOYAGE:
            vehicle_length_meters = VOYAGE_VAN_LENGTH
        else:
            vehicle_length_meters = TESLA_LENGTH
        self.px_per_m = vehicle_length_pixels / vehicle_length_meters
        self.max_accel = MAX_PIXELS_PER_SEC_SQ / self.px_per_m

        width_pixels = self.player_sprite.width
        height_pixels = self.player_sprite.height

        if self.env is None:
            self.env = Deepdrive2DEnv(
                vehicle_width=width_pixels / self.px_per_m,
                vehicle_height=height_pixels / self.px_per_m,
                px_per_m=self.px_per_m,
                add_rotational_friction=self.add_rotational_friction,
                add_longitudinal_friction=self.add_longitudinal_friction,
                return_observation_as_array=False,
                ignore_brake=False,
                expect_normalized_actions=False,
                decouple_step_time=True,
                physics_steps_per_observation=1,
                add_static_obstacle=self.static_obstacle,
                one_waypoint_map=self.one_waypoint,
            )

        self.env.reset()

        self.background = arcade.load_texture(MAP_IMAGE)

        self.player_sprite.center_x = self.env.map.x_pixels[0]
        self.player_sprite.center_y = self.env.map.y_pixels[0]

        self.player_list.append(self.player_sprite)
        self.wall_list = arcade.SpriteList()

        # self.physics_engine = arcade.PhysicsEngineSimple(self.player_sprite,
        #                                                  self.wall_list)

    def on_draw(self):
        arcade.start_render()

        e = self.env
        ppm = e.px_per_m

        angle = math.radians(self.player_sprite.angle)
        theta = angle + pi / 2

        if self.env.one_waypoint_map:
            arcade.draw_circle_filled(
                center_x=e.map.x_pixels[1],
                center_y=e.map.y_pixels[1],
                radius=20,
                color=color.ORANGE)
            if self.static_obstacle:
                static_obst_pixels = e.map.static_obst_pixels
                arcade.draw_line(
                    static_obst_pixels[0][0],
                    static_obst_pixels[0][1],
                    static_obst_pixels[1][0],
                    static_obst_pixels[1][1],
                    color=color.BLACK_OLIVE,
                    line_width=5,
                )
        else:
            # Draw the background texture
            bg_scale = 1.1
            arcade.draw_texture_rectangle(
                MAP_WIDTH_PX // 2 + SCREEN_MARGIN,
                MAP_HEIGHT_PX // 2 + SCREEN_MARGIN,
                MAP_WIDTH_PX * bg_scale,
                MAP_HEIGHT_PX * bg_scale,
                self.background)

        if e.ego_rect is not None and DRAW_COLLISION_BOXES:


            arcade.draw_rectangle_outline(
                center_x=e.x * ppm, center_y=e.y * ppm,
                width=e.vehicle_width * ppm,
                height=e.vehicle_height * ppm, color=color.LIME_GREEN,
                border_width=2, tilt_angle=math.degrees(e.angle),
            )
            arcade.draw_points(point_list=(e.ego_rect * ppm).tolist(),
                               color=color.YELLOW, size=3)

        if e.front_to_waypoint is not None and DRAW_WAYPOINT_VECTORS:
            ftw = e.front_to_waypoint

            fy = e.front_y
            fx = e.front_x


            # arcade.draw_line(
            #     start_x=e.front_x * ppm,
            #     start_y=e.front_y * ppm,
            #     end_x=(e.front_x + ftw[0]) * ppm,
            #     end_y=(e.front_y + ftw[1]) * ppm,
            #     color=c.LIME_GREEN,
            #     line_width=2,
            # )

            arcade.draw_line(
                start_x=fx * ppm,
                start_y=fy * ppm,
                end_x=(fx + cos(theta - e.angle_to_waypoint) * e.distance_to_end ) * ppm,
                end_y=(fy + sin(theta - e.angle_to_waypoint) * e.distance_to_end ) * ppm,
                color=color.PURPLE,
                line_width=2,
            )

            # Center to front length
            ctf = e.vehicle_height / 2

            arcade.draw_line(
                start_x=e.x * ppm,
                start_y=e.y * ppm,
                end_x=(e.x + cos(theta) * 20 ) * ppm,
                end_y=(e.y + sin(theta) * 20 ) * ppm,
                color=color.LIGHT_RED_OCHRE,
                line_width=2,
            )

            arcade.draw_line(
                start_x=fx * ppm,
                start_y=fy * ppm,
                end_x=(fx + e.heading[0]) * ppm,
                end_y=(fy + e.heading[1]) * ppm,
                color=color.BLUE,
                line_width=2,
            )

            arcade.draw_circle_filled(
                center_x=fx * ppm,
                center_y=fy * ppm,
                radius=5,
                color=color.YELLOW)

            arcade.draw_circle_filled(
                center_x=e.x * ppm,
                center_y=e.y * ppm,
                radius=5,
                color=color.WHITE_SMOKE,)

            arcade.draw_circle_filled(
                center_x=e.static_obstacle_points[0][0] * ppm,
                center_y=e.static_obstacle_points[0][1] * ppm,
                radius=5,
                color=color.WHITE_SMOKE,)

            arcade.draw_circle_filled(
                center_x=e.static_obstacle_points[1][0] * ppm,
                center_y=e.static_obstacle_points[1][1] * ppm,
                radius=5,
                color=color.WHITE_SMOKE,)

            if e.static_obst_angle_info is not None:

                start_obst_dist, end_obst_dist, start_obst_angle, end_obst_angle = \
                    e.static_obst_angle_info

                # start_obst_theta = start_obst_angle
                # arcade.draw_line(
                #     start_x=fx * ppm,
                #     start_y=fy * ppm,
                #     end_x=(fx + cos(start_obst_theta) * start_obst_dist) * ppm,
                #     end_y=(fy + sin(start_obst_theta) * start_obst_dist) * ppm,
                #     color=c.BLACK,
                #     line_width=2,)

                # log.info('DRAWING LINES')

                arcade.draw_line(
                    start_x=fx * ppm,
                    start_y=fy * ppm,
                    end_x=(fx + cos(theta - start_obst_angle) * start_obst_dist ) * ppm,
                    end_y=(fy + sin(theta - start_obst_angle) * start_obst_dist ) * ppm,
                    color=color.BLUE,
                    line_width=2,)

                p_x = e.front_x + cos(theta + pi / 6) * 20
                p_y = e.front_y + sin(theta + pi / 6) * 20
                pole_test = np.array((p_x, p_y))
                pole_angle = e.get_angle_to_point(pole_test)

                arcade.draw_circle_filled(
                    center_x=pole_test[0] * ppm,
                    center_y=pole_test[1] * ppm,
                    radius=5,
                    color=color.WHITE_SMOKE, )


                arcade.draw_line(
                    start_x=fx * ppm,
                    start_y=fy * ppm,
                    end_x=(fx + cos((angle + math.pi / 2) - pole_angle) * 20 ) * ppm,
                    end_y=(fy + sin((angle + math.pi / 2) - pole_angle) * 20 ) * ppm,
                    color=color.BRIGHT_GREEN,
                    line_width=2,)


                # arcade.draw_line(
                #     start_x=fx * ppm,
                #     start_y=fy * ppm,
                #     end_x=(fx + cos((angle + math.pi / 2) - end_obst_angle) * end_obst_dist) * ppm,
                #     end_y=(fy + sin((angle + math.pi / 2) - end_obst_angle) * end_obst_dist) * ppm,
                #     color=c.RED,
                #     line_width=2,)


                arcade.draw_line(
                    start_x=fx * ppm,
                    start_y=fy * ppm,
                    end_x=(e.static_obstacle_points[1][0]) * ppm,
                    end_y=(e.static_obstacle_points[1][1]) * ppm,
                    color=color.RED,
                    line_width=2,)

        if DRAW_INTERSECTION:
            self.draw_intersection()

        # arcade.draw_line(300, 300, 300 + self.player_sprite.height, 300,
        #                  arcade.color.WHITE)
        # arcade.draw_lines(self.map, arcade.color.ORANGE, 3)
        # arcade.draw_point(self.heading_x, self.heading_y,
        #                   arcade.color.WHITE, 10)

        self.player_list.draw()  # Draw the car


    def draw_intersection(self):
        bottom_horiz, left_vert, mid_horiz, mid_vert, right_vert, top_horiz = get_intersection()

        self.draw_intersection_line(left_vert)
        self.draw_intersection_line(mid_vert)
        self.draw_intersection_line(right_vert)
        self.draw_intersection_line(top_horiz)
        self.draw_intersection_line(mid_horiz)
        self.draw_intersection_line(bottom_horiz)

    def draw_intersection_line(self, line):
        line = line * self.px_per_m
        arcade.draw_line(
            line[0][0], line[0][1], line[1][0], line[1][1],
            color=color.GREEN,
            line_width=2,
        )

    def on_key_press(self, key, modifiers):
        """Called whenever a key is pressed. """
        if key == arcade.key.UP or key == arcade.key.W:
            self.accel = MAX_METERS_PER_SEC_SQ
        elif key == arcade.key.DOWN or key == arcade.key.S:
            self.accel = -MAX_METERS_PER_SEC_SQ
        elif key == arcade.key.SPACE:
            self.brake = True
        elif key == arcade.key.LEFT or key == arcade.key.A:
            self.steer = math.pi * PLAYER_TURN_RADIANS_PER_KEYSTROKE
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.steer = -math.pi * PLAYER_TURN_RADIANS_PER_KEYSTROKE

    def on_key_release(self, key, modifiers):
        """Called when the user releases a key. """

        if key == arcade.key.UP or key == arcade.key.W:
            self.accel = 0
        elif key == arcade.key.DOWN or key == arcade.key.S:
            self.accel = 0
        elif key == arcade.key.SPACE:
            self.brake = False
        elif key == arcade.key.LEFT or key == arcade.key.A:
            self.steer = 0
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.steer = 0

    def update(self, _delta_time):
        """ Movement and game logic """

        # self.bike_model.velocity += self.accel
        log.trace(f'v:{self.env.speed}')
        log.trace(f'a:{self.accel}')
        log.trace(f'dt2:{_delta_time}')

        if self.human_controlled:
            obz, reward, done, info = self.env.step(
                [self.steer, self.accel, self.brake])
            if done:
                self.env.reset()
                return

        # log.debug(f'Deviation: '
        #           f'{obz.lane_deviation / self.rough_pixels_per_meter}')

        self.player_sprite.center_x = self.env.x * self.px_per_m
        self.player_sprite.center_y = self.env.y * self.px_per_m

        # TODO: Change rotation axis to rear axle (now at center)
        self.player_sprite.angle = math.degrees(self.env.angle)

        log.trace(f'x:{self.env.x}')
        log.trace(f'y:{self.env.y}')
        log.trace(f'angle:{self.player_sprite.angle}')




def start(env=None, fps=60):
    player = Deepdrive2DPlayer(
        add_rotational_friction='--rotational-friction' in sys.argv,
        add_longitudinal_friction='--longitudinal-friction' in sys.argv,
        static_obstacle='--static-obstacle' in sys.argv,
        one_waypoint='--one-waypoint-map' in sys.argv,
        env=env,
        fps=fps,
    )
    player.setup()
    if 'DISABLE_GC' in os.environ:
        import gc
        log.warning('Disabling garbage collection!')
        gc.disable()

    if env is None:
        arcade.run()

    return player


if __name__ == "__main__":
    start()
