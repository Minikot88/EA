from ml.virtual_original_basket import OriginalConfig, Tick, simulate_original_basket


def ticks(*prices: float) -> list[Tick]:
    return [Tick(timestamp=index * 60, bid=price - 0.1, ask=price + 0.1) for index, price in enumerate(prices)]


def test_first_buy_and_sell_open_at_exactly_point_zero_one_lot() -> None:
    config = OriginalConfig(lots=0.01, distance=10, pending=10, take_profit=50, max_order=5)
    for side in ("BUY", "SELL"):
        outcome = simulate_original_basket(side, ticks(100, 100.1), config)
        assert outcome.orders[0].side == side
        assert outcome.orders[0].volume == 0.01


def test_adverse_distance_creates_and_fills_pending_lot_plus_recovery_with_step_and_cap() -> None:
    config = OriginalConfig(
        lots=0.01,
        distance=1,
        pending=1,
        take_profit=50,
        max_order=5,
        lot_type="lot_plus",
        lot_plus=0.01,
        max_lot=0.02,
        volume_step=0.01,
    )
    outcome = simulate_original_basket("BUY", ticks(100, 98.5, 100.5), config)
    assert [order.kind for order in outcome.orders] == ["MARKET", "PENDING", "MARKET"]
    assert [order.volume for order in outcome.orders] == [0.01, 0.02, 0.02]


def test_buy_honors_max_order_while_sell_preserves_original_recovery_asymmetry() -> None:
    config = OriginalConfig(lots=0.01, distance=1, pending=1, take_profit=50, max_order=1, lot_plus=0.01)
    buy = simulate_original_basket("BUY", ticks(100, 98.5, 97.5, 96.5), config)
    sell = simulate_original_basket("SELL", ticks(100, 102, 100.5, 102, 100.5, 102, 100.5), config)
    assert buy.market_order_count == 1
    assert sell.market_order_count > config.max_order


def test_basket_tp_close_and_outcome_track_duration_and_max_drawdown() -> None:
    config = OriginalConfig(lots=0.01, distance=1, pending=1, take_profit=1, max_order=5, max_duration_hours=1)
    outcome = simulate_original_basket("BUY", ticks(100, 99, 101.5), config)
    assert outcome.closed_by == "BASKET_TP"
    assert outcome.profit > 0
    assert outcome.duration_hours <= 1
    assert outcome.max_dd_percent > 0


def test_original_trailing_stop_and_money_close_are_simulated() -> None:
    trailing = OriginalConfig(
        take_profit=50,
        trailing_start=1,
        trailing_stop=0.5,
        secure_profit=0,
    )
    trailed = simulate_original_basket("BUY", ticks(100, 101.5, 100.5), trailing)
    assert trailed.closed_by == "TRAILING_SL"
    assert "TRAILING_SL" in trailed.close_events

    money = OriginalConfig(
        take_profit=50,
        tp_money=0.005,
        trailing_start=0,
        trailing_stop=0,
        secure_profit=0,
    )
    closed = simulate_original_basket("BUY", ticks(100, 101), money)
    assert closed.closed_by == "TP2_MONEY"


def test_original_secure_profit_closes_extreme_pair_only() -> None:
    config = OriginalConfig(
        distance=1,
        pending=1,
        take_profit=50,
        max_order=5,
        secure_profit=0.1,
        trailing_start=0,
        trailing_stop=0,
    )
    outcome = simulate_original_basket(
        "BUY", ticks(100, 98.5, 100.5, 97.5, 99.5, 101.5), config
    )
    assert "SECURE_PAIR" in outcome.close_events
    assert outcome.closed_by is None
