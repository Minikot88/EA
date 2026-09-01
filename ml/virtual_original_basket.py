"""Deterministic virtual execution of Kurama Original's one-sided basket.

The labeler runs this module twice at every candidate timestamp: once with a
forced first BUY and once with a forced first SELL.  It deliberately preserves
the Original source's asymmetric MaxOrder check (BUY recovery is capped while
SELL recovery is not).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, log10
from typing import Literal, Sequence


Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Tick:
    timestamp: float
    bid: float
    ask: float


@dataclass(frozen=True)
class OriginalConfig:
    lots: float = 0.01
    distance: float = 100.0
    pending: float = 100.0
    take_profit: float = 500.0
    max_order: int = 99
    lot_type: str = "lot_plus"
    lot_plus: float = 0.01
    lot_exponent: float = 1.5
    max_lot: float = 3.0
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    pip_size: float = 1.0
    tick_size: float = 1.0
    tick_value: float = 1.0
    initial_balance: float = 10_000.0
    timeframe_seconds: int = 60
    max_duration_hours: float = 24.0
    sleep_seconds: float = 5.0
    trailing_start: float = 100.0
    trailing_stop: float = 60.0
    tp_money: float = 0.0
    sl_money: float = 0.0
    tp_percent: float = 0.0
    sl_percent: float = 0.0
    secure_profit: float = 50.0


@dataclass(frozen=True)
class OrderEvent:
    side: Side
    volume: float
    price: float
    kind: Literal["MARKET", "PENDING"]
    timestamp: float


@dataclass(frozen=True)
class BasketOutcome:
    side: Side
    orders: tuple[OrderEvent, ...]
    closed_by: str | None
    profit: float
    duration_hours: float
    max_dd_percent: float
    close_events: tuple[str, ...] = ()

    @property
    def market_order_count(self) -> int:
        return sum(order.kind == "MARKET" for order in self.orders)


@dataclass
class _Position:
    volume: float
    price: float
    timestamp: float
    stop_loss: float = 0.0
    take_profit: float = 0.0


@dataclass
class _Pending:
    volume: float
    price: float


def _normalization_digits(step: float) -> int:
    if 0 < step < 1:
        return int(ceil(-log10(step)))
    return 2


def _normalize_lot(lot: float, config: OriginalConfig) -> float:
    lot = min(lot, config.max_lot)
    if config.volume_max > 0:
        lot = min(lot, config.volume_max)
    if config.volume_min > 0:
        lot = max(lot, config.volume_min)
    if config.volume_step > 0:
        # Epsilon only protects exact decimal steps from binary representation;
        # behavior remains MathFloor(lot/step)*step as in the EA.
        lot = floor((lot / config.volume_step) + 1e-12) * config.volume_step
    return round(lot, _normalization_digits(config.volume_step))


def _next_lot(positions: Sequence[_Position], config: OriginalConfig) -> float:
    if config.lot_type == "lot_plus":
        raw = round(positions[-1].volume + config.lot_plus, 2)
    elif config.lot_type == "lot_multiply":
        raw = config.lots
        for _ in range(len(positions)):
            raw = round(raw * config.lot_exponent, 8)
    else:
        raw = config.lots
    return _normalize_lot(min(raw, config.max_lot), config)


def _weighted_average(positions: Sequence[_Position]) -> float:
    volume = sum(position.volume for position in positions)
    return sum(position.price * position.volume for position in positions) / volume


def _floating_profit(
    side: Side, positions: Sequence[_Position], tick: Tick, config: OriginalConfig
) -> float:
    exit_price = tick.bid if side == "BUY" else tick.ask
    direction = 1.0 if side == "BUY" else -1.0
    return sum(
        direction
        * (exit_price - position.price)
        / config.tick_size
        * config.tick_value
        * position.volume
        for position in positions
    )


def _position_profit(
    side: Side, position: _Position, tick: Tick, config: OriginalConfig
) -> float:
    return _floating_profit(side, (position,), tick, config)


def _validate(side: str, ticks: Sequence[Tick], config: OriginalConfig) -> Side:
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if not ticks:
        raise ValueError("at least one tick is required")
    if config.initial_balance <= 0 or config.tick_size <= 0 or config.pip_size <= 0:
        raise ValueError("balance, tick size and pip size must be positive")
    if config.timeframe_seconds <= 0 or config.max_duration_hours <= 0:
        raise ValueError("timeframe and duration must be positive")
    previous_time = float("-inf")
    for tick in ticks:
        if tick.timestamp < previous_time:
            raise ValueError("ticks must be chronological")
        if tick.ask < tick.bid:
            raise ValueError("ask must be greater than or equal to bid")
        previous_time = tick.timestamp
    return side  # type: ignore[return-value]


def simulate_original_basket(
    side: Side, ticks: Sequence[Tick], config: OriginalConfig | None = None
) -> BasketOutcome:
    """Force Original's first side and replay its grid on a chronological tick slice."""

    config = config or OriginalConfig()
    side = _validate(side, ticks, config)
    first = ticks[0]
    first_price = first.ask if side == "BUY" else first.bid
    first_lot = _normalize_lot(config.lots, config)
    initial_target = 0.0
    if config.take_profit > 0:
        target_distance = config.take_profit * config.pip_size
        initial_target = (
            first_price + target_distance
            if side == "BUY"
            else first_price - target_distance
        )
    positions = [
        _Position(
            volume=first_lot,
            price=first_price,
            timestamp=first.timestamp,
            take_profit=initial_target,
        )
    ]
    events = [OrderEvent(side, first_lot, first_price, "MARKET", first.timestamp)]
    close_events: list[str] = []
    pending: _Pending | None = None
    sleep_until = first.timestamp + config.sleep_seconds
    last_recovery_bar: int | None = None
    closed_by: str | None = None
    realized_profit = 0.0
    max_dd_percent = 0.0
    final_tick = first

    def update_drawdown(tick: Tick) -> None:
        nonlocal max_dd_percent
        balance = config.initial_balance + realized_profit
        floating = _floating_profit(side, positions, tick, config)
        drawdown = (
            max(0.0, -floating / balance * 100) if balance > 0 else float("inf")
        )
        max_dd_percent = max(max_dd_percent, drawdown)

    def close_all(reason: str, tick: Tick) -> None:
        nonlocal positions, pending, realized_profit, closed_by
        realized_profit += _floating_profit(side, positions, tick, config)
        positions = []
        pending = None
        closed_by = reason
        close_events.append(reason)

    def close_indices(indices: set[int], reason: str, tick: Tick) -> None:
        nonlocal positions, realized_profit
        realized_profit += sum(
            _position_profit(side, position, tick, config)
            for index, position in enumerate(positions)
            if index in indices
        )
        positions = [
            position for index, position in enumerate(positions) if index not in indices
        ]
        close_events.append(reason)

    update_drawdown(first)
    horizon_seconds = config.max_duration_hours * 3600.0

    for tick in ticks[1:]:
        if tick.timestamp - first.timestamp > horizon_seconds:
            break
        final_tick = tick

        # Server-side pending activation and already-installed TP/SL execute even
        # while the EA is in its five-second Sleep.
        if pending is not None:
            triggered = (
                tick.ask >= pending.price if side == "BUY" else tick.bid <= pending.price
            )
            if triggered:
                fill_price = tick.ask if side == "BUY" else tick.bid
                positions.append(
                    _Position(pending.volume, fill_price, timestamp=tick.timestamp)
                )
                events.append(
                    OrderEvent(side, pending.volume, fill_price, "MARKET", tick.timestamp)
                )
                pending = None

        server_closed: set[int] = set()
        server_reason = ""
        for index, position in enumerate(positions):
            stop_hit = position.stop_loss > 0 and (
                tick.bid <= position.stop_loss
                if side == "BUY"
                else tick.ask >= position.stop_loss
            )
            target_hit = position.take_profit > 0 and (
                tick.bid >= position.take_profit
                if side == "BUY"
                else tick.ask <= position.take_profit
            )
            if stop_hit or target_hit:
                server_closed.add(index)
                server_reason = "TRAILING_SL" if stop_hit else "BASKET_TP"
        if server_closed:
            close_indices(server_closed, server_reason, tick)
        update_drawdown(tick)
        if not positions:
            pending = None
            closed_by = server_reason
            break

        if tick.timestamp < sleep_until:
            continue

        # Awake OnTick: scan the basket, then attempt common TP modifications.
        average = _weighted_average(positions)
        if config.take_profit > 0:
            target_distance = config.take_profit * config.pip_size
            target = (
                average + target_distance
                if side == "BUY"
                else average - target_distance
            )
            target_is_valid = tick.bid < target if side == "BUY" else tick.ask > target
            if target_is_valid:
                for position in positions:
                    position.take_profit = target

        # Original trailing modifies SL before recovery and close-by-money flows.
        if config.trailing_start > 0 and config.trailing_stop > 0:
            activation = config.trailing_start * config.pip_size
            stop_distance = config.trailing_stop * config.pip_size
            if side == "BUY" and tick.bid >= average + activation:
                candidate_stop = tick.bid - stop_distance
                for position in positions:
                    if candidate_stop > position.stop_loss:
                        position.stop_loss = candidate_stop
            elif side == "SELL" and tick.ask <= average - activation:
                candidate_stop = tick.ask + stop_distance
                for position in positions:
                    if position.stop_loss == 0 or candidate_stop < position.stop_loss:
                        position.stop_loss = candidate_stop

        current_bar = int(tick.timestamp // config.timeframe_seconds)
        last_position_bar = int(positions[-1].timestamp // config.timeframe_seconds)
        is_later_bar = current_bar > last_position_bar
        is_new_recovery_bar = current_bar != last_recovery_bar
        distance = config.distance * config.pip_size
        pending_distance = config.pending * config.pip_size

        if pending is None and is_later_bar and is_new_recovery_bar:
            if side == "BUY":
                candidate = tick.ask + pending_distance
                minimum = min(position.price for position in positions)
                eligible = (
                    len(positions) < config.max_order
                    and candidate < minimum
                    and minimum - tick.ask > distance
                )
            else:
                candidate = tick.bid - pending_distance
                maximum = max(position.price for position in positions)
                # Intentionally no MaxOrder condition: this is Original parity.
                eligible = candidate > maximum and tick.bid - maximum > distance
            if eligible:
                volume = _next_lot(positions, config)
                pending = _Pending(volume, candidate)
                events.append(
                    OrderEvent(side, volume, candidate, "PENDING", tick.timestamp)
                )
                last_recovery_bar = current_bar
                sleep_until = tick.timestamp + config.sleep_seconds
                continue

        # Original continuously moves stops toward the adverse market, never away.
        if pending is not None:
            candidate = (
                tick.ask + pending_distance
                if side == "BUY"
                else tick.bid - pending_distance
            )
            if side == "BUY" and pending.price > candidate:
                pending.price = candidate
            elif side == "SELL" and pending.price < candidate:
                pending.price = candidate

        floating = _floating_profit(side, positions, tick, config)
        balance = config.initial_balance + realized_profit
        if config.tp_money > 0 and floating >= config.tp_money:
            close_all("TP2_MONEY", tick)
            break
        if config.sl_money > 0 and floating <= -config.sl_money:
            close_all("SL2_MONEY", tick)
            break
        if config.sl_percent > 0 and floating <= -(config.sl_percent * balance / 100):
            close_all("SL3_PERCENT", tick)
            break
        if config.tp_percent > 0 and floating >= config.tp_percent * balance / 100:
            close_all("TP3_PERCENT", tick)
            break

        if len(positions) > 2 and config.secure_profit > 0:
            maximum_index = max(range(len(positions)), key=lambda i: positions[i].price)
            minimum_index = min(range(len(positions)), key=lambda i: positions[i].price)
            extreme_indices = {maximum_index, minimum_index}
            extreme_profit = sum(
                _position_profit(side, positions[index], tick, config)
                for index in extreme_indices
            )
            if extreme_profit > positions[-1].volume * config.secure_profit:
                close_indices(extreme_indices, "SECURE_PAIR", tick)
                update_drawdown(tick)
                if not positions:
                    pending = None
                    closed_by = "SECURE_PAIR"
                    break

    if closed_by is None:
        profit = realized_profit + _floating_profit(side, positions, final_tick, config)
    else:
        profit = realized_profit
    duration = max(0.0, (final_tick.timestamp - first.timestamp) / 3600.0)
    return BasketOutcome(
        side=side,
        orders=tuple(events),
        closed_by=closed_by,
        profit=profit,
        duration_hours=duration,
        max_dd_percent=max_dd_percent,
        close_events=tuple(close_events),
    )
