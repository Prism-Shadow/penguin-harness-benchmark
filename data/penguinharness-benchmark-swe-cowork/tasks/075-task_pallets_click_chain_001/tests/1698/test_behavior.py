import io
import pytest
import click


@pytest.mark.parametrize('threshold,updates,expected', [
    (5, [3, 2, 1, 6], [(3, 0), (0, 5), (1, 5), (0, 12)]),
    (1, [0, 1, 2], [(0, 0), (0, 1), (0, 3)]),
    (3, [1, 1, 4, 0, 3], [(1, 0), (2, 0), (0, 6), (0, 6), (0, 9)]),
])
def test_progress_bar_batches_small_updates(threshold, updates, expected):
    bar = click.progressbar(length=50, file=io.StringIO(), update_min_steps=threshold)
    observed = []
    for step in updates:
        bar.update(step)
        observed.append((bar._completed_intervals, bar.pos))
    assert observed == expected
