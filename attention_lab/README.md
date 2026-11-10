# Attention Lab · Local Route Simulator

Explore NFL routes and defensive attention using the existing project data. No packages, external scripts, or fonts need to be installed or downloaded.

## Start

Double-click `Start Attention Lab.command`, or run this command from the project root:

```bash
python3 attention_lab/server.py --open-browser
```

Open `http://127.0.0.1:8765` in your browser. If that port is occupied, add `--port 8766`. Press Ctrl+C in the terminal to stop the server. The service listens only on localhost and does not upload data.

## Use

1. Select a game and completed-pass play. The catalog includes 122 games and 4,465 eligible plays. The default is Shenault's reception in game 2021101700, play 1621.
2. Play the replay or move the timeline to any frame before the pass release.
3. Choose the focus player and the offensive player to reroute. The focus defaults to the actual receiver. Any offensive player can be rerouted, including the receiver.
4. Click **Branch from this frame**, then change direction, speed, and duration. Alternatively, drag directly from an offensive player on the field. A direction of 0° is downfield, negative angles turn left, positive angles turn right, and ±180° runs backward.
5. Move into the simulated interval to compare field connections, total attention curves, and each defender's original and simulated weights. `pp` means percentage points. Dragging sets the direction; distance comes from speed × elapsed time, not drag length.
6. Click **Clear scenario** to restore the full observed replay. **Export JSON** saves the scenario settings and frame-by-frame comparison.

## Simulation assumptions

- Only the selected offensive player changes course, moving in a straight line at constant speed from their observed position at the branch frame.
- Defenders, other offensive players, and the ball follow their observed trajectories. The simulator does not predict defensive reactions, tactical feasibility, pass placement, or reception outcomes.
- The player stops at the field boundary rather than sliding along it or continuing out of bounds.
- Simulations end within the observed pre-release window. Unknown future defender positions are never extrapolated. Clear the scenario to select another branch point anywhere in the replay.
- Attention follows the original Python model: `softmax(-distance / 5 + 2 * cos(body_orientation_to_receiver))`, with temperature 1 and normalization over receiving candidates for each defender.
- If a player outside the original route-candidate pool is selected as the focus or mover, the same player is added to **both original and simulated candidate pools**. A visible note explains the change, preventing a one-sided denominator change from appearing as a route effect.
- Original and simulated positions are identical at the branch frame, so their attention weights agree there. Differences emerge afterward.

The backend provides a read-only local data API. The interface and attention/trajectory calculations use plain JavaScript and work offline.

## Validation

```bash
python3 -B -m unittest discover -s tests -v
```

`static/core.js` contains pure calculations without DOM dependencies. It has been checked against the Python model, including candidate normalization, branch continuity, both offensive directions, boundary stops, and simulation horizons. Verification covers 32 Python tests and 1,257 JavaScript assertions. Browser checks covered game/play selection, rerouting non-route players, direct player dragging, comparison rendering, and desktop/mobile layouts.
