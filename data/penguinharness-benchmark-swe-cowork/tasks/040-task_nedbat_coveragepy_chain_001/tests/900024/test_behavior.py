import os

import pytest


@pytest.mark.parametrize('basename', ['nested/custom.data', 'different/other.data'])
def test_subprocess_preserves_full_datafile(tmp_path, basename):
    import coverage
    from coverage.config import deserialize_config
    from coverage.patch import apply_patches

    cov = coverage.Coverage(config_file=False)
    cov.config.patch = ['subprocess']
    assert cov.config.config_file is None
    cov.config.data_file = str(tmp_path / basename)
    apply_patches(cov, cov.config, cov._debug, make_pth_file=False)
    restored = deserialize_config(os.environ['COVERAGE_PROCESS_CONFIG'])
    assert restored.data_file == cov.config.data_file
    assert restored.patch == ['subprocess']
