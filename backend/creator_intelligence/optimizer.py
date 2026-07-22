"""Bounded deterministic creator-portfolio selection."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioCandidate:
    reference: str
    rate: float
    score: float
    reach: int | None


def select_portfolio(candidates: list[PortfolioCandidate], budget: float, maximum_count: int) -> list[str]:
    """Sparse dynamic programming; deterministic pruning bounds pathological input."""
    states: dict[tuple[int, float], tuple[float, int, tuple[str, ...]]] = {(0, 0.0): (0.0, 0, ())}
    for candidate in sorted(candidates, key=lambda item: item.reference):
        next_states = dict(states)
        for (count, spend), (utility, reach, refs) in states.items():
            new_spend = round(spend + candidate.rate, 2)
            if count >= maximum_count or new_spend > budget:
                continue
            key = (count + 1, new_spend)
            value = (utility + candidate.score, reach + (candidate.reach or 0), refs + (candidate.reference,))
            current = next_states.get(key)
            if current is None or (value[0], value[1], tuple(reversed(value[2]))) > (current[0], current[1], tuple(reversed(current[2]))):
                next_states[key] = value
        if len(next_states) > 5000:
            keep = sorted(next_states.items(), key=lambda item: (-item[1][0], -item[1][1], item[0][1], item[1][2]))[:5000]
            next_states = dict(keep)
        states = next_states

    viable = [(key, value) for key, value in states.items() if key[0] > 0]
    if not viable:
        return []
    _, best = max(viable, key=lambda item: (item[1][0], item[1][1], item[0][0], -item[0][1], tuple(reversed(item[1][2]))))
    return list(best[2])
