import json
import sys

import numpy as np
import pytest

from mom_esi.cli import main


def test_cli_writes_result_and_refuses_overwrite(tmp_path, monkeypatch):
    epsilon_path = tmp_path / "epsilon.npy"
    epsilon = np.ones((8, 8))
    epsilon[3:5, 3:5] = 2.0
    np.save(epsilon_path, epsilon)
    output = tmp_path / "result"
    monkeypatch.setattr(sys, "argv", ["mom-esi", str(epsilon_path), "--output", str(output)])

    main()
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["n_active"] == 4
    with np.load(output / "fields.npz") as fields:
        assert fields["E_scattered"].shape == (32, 16)
        np.testing.assert_array_equal(fields["epsilon_r"], epsilon)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
