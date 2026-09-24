# Testbed Navigation

## Purpose

`testbed_navigation` is a small, manual Nav2 integration for the starter
Testbed-T1.0.0 Gazebo Classic simulation. It deliberately starts Nav2
components directly instead of using `nav2_bringup`.

The package is designed for ROS 2 Humble on Ubuntu 22.04 with Gazebo Classic
11. It does not use Jazzy, Gazebo Harmonic, `gz_sim`, or `ros_gz_sim`.

## Architecture

```text
map_server ── /map ──> AMCL ── TF map -> odom
                              |
Gazebo diff drive ─ /odom ────+── TF odom -> base_footprint
Gazebo laser ─── /scan ───────+──> AMCL and costmap obstacle layers

planner_server (NavfnPlanner) ── global path
controller_server (DWBLocalPlanner) ── /cmd_vel ──> Gazebo diff drive
bt_navigator ── NavigateToPose workflow
behavior_server ── spin, backup, wait recovery behaviors
```

The robot interfaces are kept unchanged:

- scan: `/scan`, frame `lidar_link_1`
- odometry: `/odom`, transform `odom -> base_footprint`
- velocity command: `/cmd_vel`
- localization transform: `map -> odom`

## Package layout

```text
testbed_navigation/
├── config/
│   ├── amcl_params.yaml
│   └── nav2_params.yaml
├── launch/
│   ├── map_loader.launch.py
│   ├── localization.launch.py
│   └── navigation.launch.py
├── CMakeLists.txt
├── package.xml
└── README.md
```

## Dependencies

The package launches `nav2_map_server`, `nav2_amcl`, `nav2_planner`,
`nav2_controller`, `nav2_bt_navigator`, `nav2_behaviors`, and
`nav2_lifecycle_manager`. The existing `testbed_bringup` package supplies the
map.

## Build

From the workspace root containing this repository under `src/`:

```bash
colcon build --symlink-install
source install/setup.bash
```

## Launch order

Use separate terminals, sourcing the workspace in every terminal.

### 1. Start the existing simulation

```bash
ros2 launch testbed_bringup testbed_full_bringup.launch.py
```

### 2. Load the map

```bash
ros2 launch testbed_navigation map_loader.launch.py
```

### 3. Start localization

```bash
ros2 launch testbed_navigation localization.launch.py
```

In RViz, use **2D Pose Estimate** to publish an initial pose to `/initialpose`.
AMCL then publishes `map -> odom`.

### 4. Start navigation

```bash
ros2 launch testbed_navigation navigation.launch.py
```

Use RViz **2D Goal Pose** to publish a goal. The BT Navigator should execute
the NavigateToPose workflow and the controller should command `/cmd_vel`.

Each launch accepts `use_sim_time:=true|false`, `autostart:=true|false`, and a
parameter/map-file override where applicable. The default is simulation time
and lifecycle autostart.

## Lifecycle management

Three lifecycle managers keep responsibilities independent:

| Launch | Managed node(s) |
|---|---|
| Map loader | `map_server` |
| Localization | `amcl` |
| Navigation | `controller_server`, `planner_server`, `behavior_server`, `bt_navigator` |

With `autostart:=true`, each manager configures then activates its listed
nodes. Check that nodes are active before assuming a component can serve maps,
localize, or navigate:

```bash
ros2 lifecycle get /map_server
ros2 lifecycle get /amcl
ros2 lifecycle get /planner_server
ros2 lifecycle get /controller_server
ros2 lifecycle get /bt_navigator
ros2 lifecycle get /behavior_server
```

## Parameter decisions

- **AMCL frames:** `map`, `odom`, and `base_footprint` match the starter
  Gazebo differential-drive plugin and robot Xacro.
- **AMCL scan:** `scan_topic: scan`; the LaserScan header frame is
  `lidar_link_1` and its transform comes from `robot_state_publisher`.
- **AMCL range:** laser likelihood/range parameters are capped at `1.5 m`, the
  simulated lidar maximum.
- **Global costmap:** uses `map`, the static map, scan obstacles, and a
  `0.25 m` conservative radius.
- **Local costmap:** uses a rolling `3 m x 3 m` window in `odom`, scan
  obstacles, and the same footprint approximation.
- **Planner:** Navfn is selected as the simple, grid-based Level-1 global
  planner. `use_astar: false` keeps its standard Dijkstra-style behavior.
- **Controller:** DWB uses conservative `0.20 m/s` linear and `1.0 rad/s`
  angular limits. These are starting values, not measured hardware limits.
- **Behaviors:** only Spin, BackUp, and Wait are configured to support the
  default recovery-oriented navigation tree without optional features.

## Bugs discovered and fixed

See the root-level `BUGS_FIXED.txt`. It records four starter issues and keeps
static confirmation separate from required local runtime verification.

## Local verification checklist

Mark results only after testing in Ubuntu 22.04, ROS 2 Humble, and Gazebo
Classic 11.

- [ ] TEST-01: `colcon build --symlink-install` succeeds.
- [ ] TEST-02: `testbed_full_bringup.launch.py` starts Gazebo and RViz.
- [ ] TEST-03: `ros2 topic echo /scan --once` receives LaserScan data.
- [ ] TEST-04: `ros2 topic echo /odom --once` receives odometry.
- [ ] TEST-05: `ros2 run tf2_ros tf2_echo odom base_footprint` resolves.
- [ ] TEST-06: `ros2 run tf2_ros tf2_echo base_footprint lidar_link_1` resolves.
- [ ] TEST-07: map server becomes active and `/map` appears in RViz.
- [ ] TEST-08: AMCL becomes active and accepts `/initialpose`.
- [ ] TEST-09: AMCL publishes `map -> odom` and localization remains stable.
- [ ] TEST-10: planner, controller, behavior, and BT Navigator are active.
- [ ] TEST-11: a 2D goal creates a global path.
- [ ] TEST-12: `/cmd_vel` is published while navigating.
- [ ] TEST-13: the robot reaches a reachable goal.
- [ ] TEST-14: scan obstacles influence the local trajectory where the map and
      environment support this test.

## Known limitations

- This implementation has not been run in this repository's development
  environment because it does not contain ROS 2 Humble, Gazebo Classic, or
  colcon. All runtime results require local verification.
- The `0.25 m` robot radius and DWB limits are conservative starting values;
  tune only after observing the simulated robot.
- The existing `full_bringup.rviz` is a baseline visualization configuration.
  Add Map, ParticleCloud, Path, and Costmap displays during local testing if
  needed; this package intentionally does not replace that starter RViz file.
- No velocity smoother, collision monitor, custom visualization, or other
  optional Nav2 feature is included.

## Interview guide

### map_server

`map_server` loads the supplied occupancy-grid YAML/PGM and publishes `/map`.
It is lifecycle-managed because Nav2 should not consume map data until loading
has succeeded. It does not localize or plan.

### AMCL

AMCL is a particle-filter localizer. It compares `/scan` laser observations to
`/map`, uses `/odom` for motion updates, and publishes the correction
transform `map -> odom`. In this project its key contract is `map`, `odom`,
`base_footprint`, and `/scan`; a missing laser-to-base TF or an initial pose
prevents useful localization.

### Costmaps

The global costmap uses `map` to support global planning. The local rolling
costmap uses `odom` so it can update near the robot even as AMCL corrects the
map-to-odom transform. Both use `/scan` as an obstacle source and inflation to
keep the robot away from obstacles.

### NavfnPlanner

`NavfnPlanner` makes a grid-based global path through the global costmap. It
is an understandable Level-1 choice: it searches free occupancy/costmap cells
between start and goal. A* is an alternative, but this configuration retains
Navfn's standard Dijkstra-style behavior for simplicity.

### DWBLocalPlanner

DWB samples feasible linear/angular trajectories, scores them against obstacle,
path-alignment, path-distance, goal-alignment, and goal-distance critics, then
sends the best command to `/cmd_vel`. Typical failure modes are an incorrect
robot footprint, missing `/scan`, overly aggressive velocity/acceleration
limits, or a missing odom/base TF.

### BT Navigator

`bt_navigator` exposes the `NavigateToPose` action and coordinates planning,
control, and recoveries through a behavior tree. It is not the planner or
controller itself; it decides the sequence of calls and recovery behavior.

### Behavior Server

The behavior server provides reusable Spin, BackUp, and Wait actions used by
the recovery-capable navigation tree. It can fail when its costmap/TF inputs
are unavailable or collision checking prevents the requested behavior.

### Lifecycle managers

Nav2 nodes are lifecycle nodes. A lifecycle manager transitions its named
nodes from unconfigured to inactive to active. Separate managers preserve the
assignment's modular map, localization, and navigation launches.
