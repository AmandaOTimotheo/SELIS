import os
import random
import pandas as pd


# --------------------------------------------------------------------------------------------------
# BINOMIAL PROBABILITY MODEL FOR MESSAGE COLLISION
# --------------------------------------------------------------------------------------------------
def simulate_collision_analysis(p):
    print("\n" + "-" * 100 + "\n" + "-" * 100)
    print("[Collision] Starting collision analysis...")
    """
    Performs collision analysis (statistical + simulation)
    using the parameters provided in `p`.
    """
    collision_cfg = p.collision

    results = []

    if collision_cfg.poisson_calculation_enable:
        lambda_per_edge = 1.0 / collision_cfg.transmission_interval_edge

        success, loss, rate, total_events = simulate_msg_collisions_poisson(
            num_edges=collision_cfg.num_edges,
            lambda_per_edge=lambda_per_edge,
            msg_transmission_time=collision_cfg.msg_transmission_time,
            sim_duration_seconds=collision_cfg.transmission_interval_edge,
            t_simulation_cycles=collision_cfg.t_simulation_cycles,
            num_channels=collision_cfg.num_channels,
        )

        results.append({
            "type": "statistical_poisson",
            "num_edges": collision_cfg.num_edges,
            "transmission_interval_edge": collision_cfg.transmission_interval_edge,
            "msg_transmission_time": collision_cfg.msg_transmission_time,
            "t_simulation_cycles": collision_cfg.t_simulation_cycles,
            "num_channels": collision_cfg.num_channels,
            "success": success,
            "loss": loss,
            "success_rate_percent": rate,
            "total_events": total_events,
            "lambda_per_edge": lambda_per_edge,
        })

    if collision_cfg.monte_carlo_simulation_enable:
        success, loss, rate, total_events = simulate_msg_collisions_monte_carlo(
            num_edges=collision_cfg.num_edges,
            transmission_interval_edge=collision_cfg.transmission_interval_edge,
            msg_transmission_time=collision_cfg.msg_transmission_time,
            t_simulation_cycles=collision_cfg.t_simulation_cycles,
            num_channels=collision_cfg.num_channels,
        )

        results.append({
            "type": "monte_carlo_simulation",
            "num_edges": collision_cfg.num_edges,
            "transmission_interval_edge": collision_cfg.transmission_interval_edge,
            "msg_transmission_time": collision_cfg.msg_transmission_time,
            "t_simulation_cycles": collision_cfg.t_simulation_cycles,
            "num_channels": collision_cfg.num_channels,
            "success": success,
            "loss": loss,
            "success_rate_percent": rate,
            "total_events": total_events,
        })

    if results:
        out_dir = collision_cfg.save_data_path
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, "collision_report.csv")
            pd.DataFrame(results).to_csv(out_path, index=False, sep=";", decimal=",")
            print(f"\n[Collision] Report saved to {out_path}")

    print("[Collision] Collision analysis completed.")


#-----------------------------------------------Simulator - Message Collision-----------------------------------------------------------


def simulate_msg_collisions_monte_carlo(num_edges, transmission_interval_edge, msg_transmission_time,
                                        t_simulation_cycles, num_channels):
    """
    Simulate message collisions in a multi-channel environment.

    Args:
        num_edges (int): Number of edge transmitters.
        transmission_interval_edge (float): Base time interval between transmissions (seconds).
        msg_transmission_time (float): Duration of each message (seconds).
        t_simulation_cycles (int): Number of cycles to simulate (higher = longer sim).
        num_channels (int): Number of available channels.

    Returns:
        tuple: (success_count, loss_count, success_rate, total_events)
    """
    print(f"\n[Simulation] Starting collision simulation for {num_edges} edges "
          f"over {t_simulation_cycles} cycles...")

    clock_range = [msg_transmission_time / 2, msg_transmission_time]
    total_time = t_simulation_cycles * num_edges

    transmitters = [
        {
            "start_time": random.uniform(0, transmission_interval_edge),
            "bias": random.uniform(*clock_range)
        }
        for _ in range(num_edges)
    ]

    events = []
    for tx in transmitters:
        t = tx["start_time"]
        while t < total_time:
            delay = transmission_interval_edge + random.uniform(0, 1) + tx["bias"]
            start_time = t + delay
            end_time = start_time + msg_transmission_time
            channel = random.randint(1, num_channels)
            events.append((start_time, end_time, channel))
            t = start_time

    events.sort()

    active = {ch: [] for ch in range(1, num_channels + 1)}
    success, loss = 0, 0
    last_was_lost = False

    for start, end, ch in events:
        active[ch] = [e for e in active[ch] if e > start]

        if active[ch]:
            loss += 1
            if not last_was_lost:
                loss += 1
                success -= 1
            last_was_lost = True
        else:
            success += 1
            last_was_lost = False

        active[ch].append(end)

    total = success + loss
    rate = (success / total) * 100 if total > 0 else 0

    print(f"[Simulation Result]")
    print(f"  Successful transmissions: {success}")
    print(f"  Lost transmissions:       {loss}")
    print(f"  Success rate:              {rate:.2f}%")
    print(f"  Total events:              {len(events)}")

    return success, loss, rate, len(events)


def simulate_msg_collisions_poisson(num_edges, lambda_per_edge, msg_transmission_time,
                                    sim_duration_seconds, t_simulation_cycles, num_channels):
    """
    Simulação alternativa: chegadas de pacotes por edge com intervalos exponenciais
    (processo de Poisson). Considera colisão se intervalos se sobrepõem no mesmo canal.

    Args:
        num_edges (int): número de transmissores.
        lambda_per_edge (float): taxa média de chegadas por edge (eventos/segundo).
        msg_transmission_time (float): duração de cada mensagem (segundos).
        sim_duration_seconds (float): tempo total de simulação.
        t_simulation_cycles (int): quantidade de ciclos simulados.
        num_channels (int): quantidade de canais.

    Returns:
        tuple: (success_count, loss_count, success_rate, total_events)
    """
    print(f"\n[Simulation-Poisson] {num_edges} edges, λ={lambda_per_edge}/s, duração={sim_duration_seconds}s")

    success, loss = 0, 0
    for _ in range(t_simulation_cycles):
        events = []
        for _ in range(num_edges):
            t = random.expovariate(lambda_per_edge)
            while t < sim_duration_seconds:
                start_time = t
                end_time = start_time + msg_transmission_time
                channel = random.randint(1, num_channels)
                events.append((start_time, end_time, channel))
                t += random.expovariate(lambda_per_edge)

        events.sort()

        active = {ch: [] for ch in range(1, num_channels + 1)}

        for start, end, ch in events:
            active[ch] = [e for e in active[ch] if e > start]

            if active[ch]:
                loss += 1
            else:
                success += 1

            active[ch].append(end)

    total = success + loss
    rate = (success / total) * 100 if total > 0 else 0
    total_events = len(events) * t_simulation_cycles
    print(f"[Simulation-Poisson Result] success={success} loss={loss} rate={rate:.2f}% events={total_events}")
    return success, loss, rate, total_events