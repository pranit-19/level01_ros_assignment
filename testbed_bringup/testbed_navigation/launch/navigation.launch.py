#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time')
    params_file = LaunchConfiguration('params_file')
    autostart = LaunchConfiguration('autostart')

    common = [params_file, {'use_sim_time': use_sim_time}]
    navigation_nodes = [
        Node(package='nav2_controller', executable='controller_server',
             name='controller_server', output='screen', parameters=common),
        Node(package='nav2_planner', executable='planner_server',
             name='planner_server', output='screen', parameters=common),
        Node(package='nav2_behaviors', executable='behavior_server',
             name='behavior_server', output='screen', parameters=common),
        Node(package='nav2_bt_navigator', executable='bt_navigator',
             name='bt_navigator', output='screen', parameters=common),
    ]

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument(
            'params_file',
            default_value=PathJoinSubstitution([
                FindPackageShare('testbed_navigation'), 'config', 'nav2_params.yaml'
            ]),
            description='Full path to the Nav2 parameter file.'),
        DeclareLaunchArgument('autostart', default_value='true'),
        *navigation_nodes,
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='navigation_lifecycle_manager',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'autostart': autostart,
                'node_names': [
                    'controller_server',
                    'planner_server',
                    'behavior_server',
                    'bt_navigator',
                ],
            }],
        ),
    ])    
