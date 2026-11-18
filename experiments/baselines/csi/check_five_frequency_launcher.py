"""Small controller checks with fake workers; never launches MATLAB or git."""
import json
from contextlib import ExitStack
from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np
from experiments.baselines.csi import campaign_five_frequency as c


def check():
    with tempfile.TemporaryDirectory(prefix='csi-five-check-') as temp:
        root = Path(temp)
        with patch.object(c, 'ROOT', root / 'results'), patch.object(c, 'DATA', root / 'data'), \
             patch.object(c, 'TRUTH', root / 'truth'), patch.object(c, 'POLICY', root / 'policy.json'):
            c.configure()
            assert c.ceiling() == 3
            c.POLICY.write_text('{"max_csi_fits": 0}')
            assert c.ceiling() == 0
            c.POLICY.write_text('{"max_csi_fits": 1}')
            assert c.ceiling() == 1
            c.POLICY.write_text('{"max_csi_fits": 1.5}')
            try:
                c.ceiling()
                raise AssertionError('noninteger policy accepted')
            except ValueError:
                pass
            c.POLICY.unlink()
            # Synthetic table fixture is local to this temporary test folder.
            # Never create a table under the frozen-data folder.
            pairs = np.array([(s, r) for s in range(1, 37) for r in range(1, 50)])
            for scene in c.SHAPES:
                forward = c.DATA / scene / 'forward'
                parent = c.TRUTH / scene / 'forward'
                truth = c.TRUTH / scene / 'truth'
                forward.mkdir(parents=True); parent.mkdir(parents=True); truth.mkdir()
                table = np.zeros((8820, 7))
                table[:, :2] = np.repeat(pairs, 5, axis=0)
                table[:, 2] = np.tile(c.FREQUENCIES, 1764)
                np.savetxt(forward / 'synthetic_input.txt', table)
                path = forward / 'synthetic_input.txt'
                path.with_suffix('.txt.sha256').write_text(c.base.sha(path) + '\n')
                old = np.zeros((14112, 7)); old[:, :2] = np.repeat(pairs, 8, axis=0)
                np.savetxt(parent / 'synthetic_input.txt', old)
                (truth / 'geometry.mat').write_bytes(b'frozen fixture')
                (truth / 'geometry.json').write_text('{}')
            assert not c.releases()
            entry = c.release('star')
            assert c.release('star') == entry
            folder = c.prepare_case(entry)
            assert json.loads((folder / 'data.json').read_text())['path'] == str(c.DATA / 'star/forward/synthetic_input.txt')
            assert not (folder / 'selected').exists()
            # Materialize the real owned driver, replacing process creation only.
            with patch.object(c.base, 'launch', return_value=dict(record={})) as start:
                c.selected.inversion('star', folder)
                text = (folder / 'executed_driver.m').read_text()
                assert 'fre = [0.5 1 1.5 2 2.5];' in text
                assert '= 2048;' in text and 'CC_CSI_Brent_recorded(' in text
                assert 'MR_CSI_Brent(' not in text and '\n[mchi3' not in text
                assert str(c.DATA / 'star/forward/synthetic_input.txt') in text
                assert start.call_count == 1
            source = (c.base.UP / 'functions/CC_CSI_Brent.m').read_text()
            recorded = (c.base.CODE / 'recorded/CC_CSI_Brent_recorded.m').read_text()
            restored = recorded.replace('CC_CSI_Brent_recorded(', 'CC_CSI_Brent(')
            restored = restored.replace('        csi_record_snapshot(jj, mchi{end}, toc(startTime));\n', '')
            assert restored == source
            path = c.DATA / 'star/forward/synthetic_input.txt'
            path.write_text(path.read_text() + '\n')
            try:
                c.frozen_input('star')
                raise AssertionError('changed frozen hash accepted')
            except ValueError:
                pass
            # Test the continuous controller with dynamic releases, limits,
            # completed resume and an expired informational time target.
            c.ROOT.mkdir(exist_ok=True)
            for p in (c.ROOT / 'star').rglob('*'):
                if p.is_file(): p.unlink()
            prepared = []
            active = []
            finished = []
            released = [dict(scene='star')]
            ticks = [0]
            limits_seen = []
            class Process:
                def poll(self):
                    return 0 if ticks[0] >= self.end else None
            def launch(scene, folder):
                process = Process(); process.end = ticks[0] + 2
                job = dict(scene=scene, folder=folder, process=process, family=0)
                assert len(active) < policy()
                active.append(job)
                (folder / 'launch.json').write_text('{}')
                return job
            def prepare(entry):
                prepared.append(entry['scene'])
                folder = c.ROOT / entry['scene'];folder.mkdir(exist_ok=True)
                return folder
            def policy():
                # Lower limit while the first job is running: no stop.
                value = 1 if ticks[0] <= 2 or ticks[0] == 4 else 3
                limits_seen.append(value)
                return value
            def sleep(seconds):
                ticks[0] += 1
                if ticks[0] == 1:
                    released.extend(dict(scene=s) for s in c.SHAPES[1:])
            def finalize(job):
                assert job in active
                active.remove(job);finished.append(job['scene'])
                c.base.write(job['folder'] / 'outcome.json', dict(state='completed', utc='fake'))
                return job['scene']
            # Source paths are hashed by run(); skip source content only.
            mocks = [patch.object(c, 'inspect', return_value=dict(ready=True)),
                 patch.object(c, 'ceiling', side_effect=policy),
                 patch.object(c, 'releases', side_effect=lambda: list(released)),
                 patch.object(c, 'prepare_case', side_effect=prepare),
                 patch.object(c.selected, 'inversion', side_effect=launch),
                 patch.object(c.selected, 'iteration_timing'),
                 patch.object(c, 'finalize', side_effect=finalize),
                 patch.object(c, 'publish'), patch.object(c, 'report'),
                 patch.object(c, 'manifest'),
                 patch.object(c, 'snapshot_status'),
                 patch.object(c.base, 'sample'), patch.object(c.base, 'sha', return_value='fake'),
                 patch.object(c.base, 'memory', return_value={'MemAvailable': 100 * c.base.GIB}),
                 patch.object(c.base, 'terminate', side_effect=AssertionError('unexpected worker stop')),
                 patch.object(c.subprocess, 'check_output', return_value='fake'),
                 patch.object(c, 'now', return_value='2026-11-18T00:00:00+00:00'),
                 patch.object(c.time, 'sleep', side_effect=sleep),
                 patch.object(c, 'TARGET_HOURS', 1e-12)]
            with ExitStack() as stack:
                for mock in mocks:
                    stack.enter_context(mock)
                c.run()
                assert finished == c.SHAPES and prepared == c.SHAPES
                assert 1 in limits_seen and 3 in limits_seen
                original = c.RECORD['started_utc']
                c.run(resume=True)
                assert c.RECORD['started_utc'] == original
                assert finished == c.SHAPES and prepared == c.SHAPES
                (c.ROOT / 'hook/outcome.json').unlink()
                c.run(resume=True)
                assert 'interrupted' in c.read(c.ROOT / 'hook/outcome.json')['state']
                assert finished == c.SHAPES and prepared == c.SHAPES
            (c.ROOT / 'STOP').touch()
            assert c.stopped()
            assert (c.ROOT / 'STOP').exists()
            with patch.object(c.selected, 'active_workers', return_value=[]):
                assert not c.inspect(resume=True)['ready']
            print(json.dumps(dict(passed=True, fake_fits=len(finished), real_fits=0,
                changing_releases=True, changing_ceiling=True, lower_ceiling_does_not_stop=True,
                resume_preserves_finished=True, expired_time_target_never_stops=True,
                interrupted_never_restarted=True, stop_preserved=True,
                native_driver_materialized_without_process=True,
                output_only_copy_matches_upstream=True,
                hash_tamper_rejected=True, no_frozen_data_writes=True)))


if __name__ == '__main__':
    check()
