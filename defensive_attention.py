"""Distance/orientation softmax baseline for NFL tracking; standard library only."""

import argparse
import csv
from dataclasses import dataclass
import math
from pathlib import Path


@dataclass(frozen=True)
class AttentionConfig:
    distance_scale: float = 5.0  # yards
    direction_weight: float = 2.0
    temperature: float = 1.0
    direction_source: str = "o"

    def __post_init__(self):
        for name in ("distance_scale", "temperature"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.direction_weight) or self.direction_weight < 0:
            raise ValueError("direction_weight must be finite and nonnegative")
        if self.direction_source not in ("o", "dir"):
            raise ValueError("direction_source must be o or dir")


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def valid_position(player):
    return number(player.get("x")) is not None and number(player.get("y")) is not None


def frame_attention(defenders, receivers, config=None):
    """Return one row per valid defender/receiver pair; normalize over receivers.

    NFL angle convention: 0 = +y, 90 = +x, clockwise. Missing heading
    contributes zero alignment; a coincident pair also has zero alignment.
    No future positions, target labels, or receiver motion enter the score.
    """
    config = config or AttentionConfig()
    receivers = [r for r in receivers if valid_position(r)]
    output = []
    for defender in defenders:
        if not valid_position(defender) or not receivers:
            continue
        heading = number(defender.get(config.direction_source))
        pairs = []
        for receiver in receivers:
            dx = float(receiver["x"]) - float(defender["x"])
            dy = float(receiver["y"]) - float(defender["y"])
            distance = math.hypot(dx, dy)
            alignment = 0.0
            if heading is not None and distance > 1e-12:
                radians = math.radians(heading % 360)
                alignment = (math.sin(radians) * dx + math.cos(radians) * dy) / distance
                alignment = max(-1.0, min(1.0, alignment))
            logit = -distance / config.distance_scale + config.direction_weight * alignment
            pairs.append({
                "defenderId": defender["nflId"],
                "receiverId": receiver["nflId"],
                "distanceYards": distance,
                "alignmentCosine": alignment,
                "headingMissing": int(heading is None),
                "logit": logit,
            })
        # Subtract before temperature scaling to avoid softmax overflow.
        maximum = max(pair["logit"] for pair in pairs)
        weights = [math.exp((p["logit"] - maximum) / config.temperature) for p in pairs]
        total = sum(weights)
        for pair, weight in zip(pairs, weights):
            pair["attention"] = weight / total
            output.append(pair)
    return output


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        yield from csv.DictReader(handle)


def iter_plays(path, selected_play=None):
    """Read a tracking file one contiguous play at a time (not one frame)."""
    key = None
    rows = []
    completed = set()
    for row in read_csv(path):
        if selected_play is not None and int(row["playId"]) != selected_play:
            continue
        current = (row["gameId"], row["playId"])
        if current != key:
            if rows:
                completed.add(key)
                yield key, rows
            if current in completed:
                raise ValueError("Tracking rows must be contiguous by gameId/playId")
            key, rows = current, []
        rows.append(row)
    if rows:
        yield key, rows


def play_attention(rows, possession_team, roles, positions, config,
                   candidate_mode="route", window="passing"):
    """Use all opposing players as defenders; no defensive PFF labels required.

    passing window = snap through first pass/release or terminal event,
    inclusive. A missing snap yields no rows. Missing terminal event uses
    the end of the observed play. 'all' includes every observed frame.
    """
    if candidate_mode not in ("route", "position") or window not in ("passing", "all"):
        raise ValueError("Unknown candidate mode or window")
    snaps = [int(r["frameId"]) for r in rows if r["event"] in ("ball_snap", "autoevent_ballsnap")]
    if window == "passing" and not snaps:
        return
    start = min(snaps) if window == "passing" else -math.inf
    endings = {"pass_forward", "autoevent_passforward", "qb_sack", "qb_strip_sack",
               "pass_shovel", "tackle", "out_of_bounds", "touchdown", "fumble"}
    ends = [int(r["frameId"]) for r in rows
            if r["event"] in endings and int(r["frameId"]) >= start]
    end = min(ends) if ends and window == "passing" else math.inf
    frames = {}
    for row in rows:
        frame = int(row["frameId"])
        if start <= frame <= end:
            frames.setdefault(frame, []).append(row)
    for frame, players in sorted(frames.items()):
        defenders, receivers = [], []
        for player in players:
            if not player["nflId"] or player["team"].lower() == "football":
                continue
            if player["team"] != possession_team:
                defenders.append(player)
            elif (candidate_mode == "route" and roles.get(player["nflId"], "").lower() == "pass route") or (
                candidate_mode == "position" and positions.get(player["nflId"]) in {"WR", "TE", "RB", "FB", "HB"}
            ):
                receivers.append(player)
        for pair in frame_attention(defenders, receivers, config):
            yield {"gameId": players[0]["gameId"], "playId": players[0]["playId"],
                   "frameId": frame, "time": players[0]["time"], **pair}


FIELDS = ["gameId", "playId", "frameId", "time", "defenderId", "receiverId",
          "distanceYards", "alignmentCosine", "headingMissing", "logit", "attention"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "nfl-big-data-bowl-regional-event-data-main/data")
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--play-id", type=int)
    parser.add_argument("--output", type=Path, default=Path("outputs/defensive_attention.csv"))
    parser.add_argument("--candidate-mode", choices=["route", "position"], default="route")
    parser.add_argument("--window", choices=["passing", "all"], default="passing")
    parser.add_argument("--distance-scale", type=float, default=5.0)
    parser.add_argument("--direction-weight", type=float, default=2.0)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--direction-source", choices=["o", "dir"], default="o")
    args = parser.parse_args()
    config = AttentionConfig(args.distance_scale, args.direction_weight, args.temperature, args.direction_source)
    plays = {(r["gameId"], r["playId"]): r for r in read_csv(args.data_dir / "plays.csv")
             if r["gameId"] == args.game_id}
    positions = {r["nflId"]: r["officialPosition"] for r in read_csv(args.data_dir / "players.csv")}
    scouting = {}
    if args.candidate_mode == "route":
        for row in read_csv(args.data_dir / "pffScoutingData.csv"):
            if row["gameId"] == args.game_id:
                scouting.setdefault((row["gameId"], row["playId"]), {})[row["nflId"]] = row["pff_role"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for key, rows in iter_plays(args.data_dir / "tracking" / f"tracking_{args.game_id}.csv", args.play_id):
            if key not in plays:
                raise ValueError(f"Missing play metadata: {key}")
            for pair in play_attention(rows, plays[key]["possessionTeam"], scouting.get(key, {}),
                                       positions, config, args.candidate_mode, args.window):
                writer.writerow(pair)
                count += 1
    if not count:
        raise SystemExit("No attention pairs produced; check play, snap event, and candidate metadata.")
    print(f"Wrote {count:,} defender-receiver rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()
