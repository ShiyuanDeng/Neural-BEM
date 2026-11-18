"""Runner for the five-frequency CSI pass (bem-csi-run). Started once, detached.

Never edits the wrapper or the solver. It
  1. runs each shape's 1% check as soon as its table is frozen (manifest state 'frozen' and a
     .sha256 beside the table), CPU, no slot; commits and pushes the check by path;
  2. starts GPU fits in plan order for shapes whose check passed, whenever fewer than
     max_bem_fits BEM workers run and the memory rule holds (resource_policy.json re-read each pass);
  3. after all ten GPU fits are over, starts the CPU cross-checks one slot at a time;
  4. commits and pushes each finished fit by path once its metrics.json exists.
It never stops or slows any process. No time limit. A failed or crashed fit is kept, never rerun.
State: logs/waiter_state.json. Alerts for the runner: logs/alerts.log.
"""
import json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/drdeng/Neural_SDF_BEM_AD_organised')
R = Path('results/bem/baseline_data/csi_five_frequency/2026-11-18')
DATA = Path('results/csi/tg002/2026-11-18_five_frequency_data')
POLICY = ROOT / 'results/csi/resource_policy.json'
PY = '/home/drdeng/miniconda3/envs/EMNerf/bin/python'
SHAPES = ['circle', 'kite', 'peanut', 'star', 'asymmetric', 'c_shape', 'hook', 'cross', 'cog', 'aphex_twin']
FLOOR_PLUS_MARGIN, WRAPPER_START, BEM_RESERVE = 16.0, 16.5, 4.0
POLL = 30
TRAILER = 'Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>'
STATE = ROOT / R / 'logs/waiter_state.json'
os.chdir(ROOT)


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def log(msg):
    print(f'{now()} {msg}', flush=True)


def alert(msg):
    log('ALERT ' + msg)
    with open(ROOT / R / 'logs/alerts.log', 'a') as f:
        f.write(f'{now()} {msg}\n')


def load():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {s: dict(check='pending', gpu='none', cpu='none') for s in SHAPES}


def save(st):
    STATE.write_text(json.dumps(st, indent=1))


def git(paths, message):
    """Commit and push by path; retry while the index is locked; never pull --rebase."""
    paths = [str(p) for p in paths if (ROOT / p).exists()]
    if not paths:
        return
    msg = f'{message}\n\n{TRAILER}'
    for _ in range(40):
        gd = subprocess.run(['git', 'rev-parse', '--git-dir'], capture_output=True, text=True).stdout.strip()
        if (ROOT / gd / 'index.lock').exists():
            time.sleep(3); continue
        a = subprocess.run(['git', 'add', '--'] + paths, capture_output=True, text=True)
        c = subprocess.run(['git', 'commit', '-q', '-m', msg, '--'] + paths, capture_output=True, text=True)
        if 'index.lock' in (a.stderr + c.stderr):
            time.sleep(3); continue
        if c.returncode not in (0, 1):
            log(f'commit problem: {c.stderr.strip()[:300]}')
        break
    for _ in range(20):
        p = subprocess.run(['git', 'push', '-q'], capture_output=True, text=True)
        if p.returncode == 0:
            return
        log(f'push retry: {p.stderr.strip()[:200]}')
        time.sleep(5)
    alert('push failed 20 times')


CSI_DIR = str(ROOT / 'results/csi/tg002/2026-11-18_five_frequency')
KIND_KEY = dict(data='matlab_data', csi='mf_cc_csi_fit', b1='bem_fit', bem='bem_fit', check='cpu_forward_check')


def jobs():
    """Same count as experiments/resource_management/watch_comparison.py (process_sample):
    a job is a root process plus ALL its descendants; RSS is summed over the whole job."""
    out = subprocess.check_output(['ps', '-u', str(os.getuid()), '-o', 'pid=,ppid=,rss=,comm=,args='], text=True)
    procs = {}
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) == 5:
            pid, parent, rss, comm, command = parts
            procs[int(pid)] = dict(parent=int(parent), rss_gib=int(rss) / 1024 ** 2, comm=comm, command=command)

    def ancestors(pid):
        seen = set()
        while pid in procs and pid not in seen:
            seen.add(pid)
            yield pid
            pid = procs[pid]['parent']

    roots = {}
    for pid, p in procs.items():
        cmd = p['command']
        if 'python' in p['comm']:
            if 'b1_run.py fit --case' in cmd:
                roots[pid] = 'b1'
            elif 'csi_fit.py' in cmd and '--case' in cmd:
                roots[pid] = 'bem'
            elif 'csi_forward_check.py' in cmd:
                roots[pid] = 'check'
        elif p['comm'] == 'MATLAB':
            context = ' '.join(procs[a]['command'] for a in ancestors(pid))
            if 'five_frequency_data' in context or 'generate_five_frequency' in context:
                roots[pid] = 'data'
            elif 'campaign_five_frequency' in context or CSI_DIR in context:
                roots[pid] = 'csi'
    res = []
    for pid, kind in roots.items():
        if any(a in roots for a in list(ancestors(pid))[1:]):
            continue
        rss = sum(p['rss_gib'] for child, p in procs.items() if pid in ancestors(child))
        res.append(dict(pid=pid, kind=kind, rss_gib=rss))
    return res


def available_gib():
    for line in open('/proc/meminfo'):
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) / 1048576


def slot_free():
    """Launch only if fewer than max_bem_fits BEM fits (B1 and csi_fit) run and
    MemAvailable - new bem_fit reservation - outstanding growth >= floor_gib + margin_gib.
    Reservations are read from worker_reservation_gib in the policy file at each pass."""
    try:
        pol = json.loads(POLICY.read_text())
        reserve = pol['worker_reservation_gib']
    except Exception as e:
        log(f'policy unreadable: {e}'); return False, 'policy unreadable'
    js = jobs()
    n_bem = sum(j['kind'] in ('b1', 'bem') for j in js)
    growth = sum(max(0.0, reserve[KIND_KEY[j['kind']]] - j['rss_gib']) for j in js)
    new = reserve['bem_fit']
    avail = available_gib()
    left = avail - new - growth
    ok = n_bem < pol['max_bem_fits'] and left >= pol.get('floor_gib', 14) + pol.get('margin_gib', 2) \
        and avail >= WRAPPER_START
    kinds = ','.join(f"{j['kind']}:{j['rss_gib']:.1f}" for j in js)
    why = f'bem={n_bem}/{pol["max_bem_fits"]} avail={avail:.1f} growth={growth:.1f} new={new} left={left:.1f} jobs=[{kinds}]'
    return ok, why


def table_ready(s):
    m = ROOT / DATA / s / 'manifest.json'
    t = ROOT / DATA / s / 'forward/synthetic_input.txt'
    try:
        return json.loads(m.read_text()).get('state') == 'frozen' and Path(str(t) + '.sha256').exists()
    except Exception:
        return False


def adopt_check(s, st):
    """A check already made by hand and committed (same table SHA-256) is adopted, not rerun."""
    case = f'{s}__c4'
    js = ROOT / R / 'adapter_checks' / f'{case}.json'
    if not js.exists():
        return False
    d = json.loads(js.read_text())
    sha = Path(str(ROOT / DATA / s / 'forward/synthetic_input.txt') + '.sha256').read_text().split()[0]
    if d['mismatch']['source']['sha256'] != sha:
        return False
    sm = d['summary']
    per = {}
    for r in d['mismatch']['per_frequency']:
        per[r['frequency_ghz']] = max(per.get(r['frequency_ghz'], 0), r['relative_mismatch'])
    st[s]['mismatch_pct'] = {str(k): round(100 * v, 4) for k, v in per.items()}
    st[s]['sha256'] = sha
    st[s]['check'] = 'pass' if (sm['adapter_checks_pass'] and sm['one_percent_rule']) else 'fail'
    save(st)
    log(f'{s} check adopted from the saved file: {st[s]["check"]}')
    return True


def run_check(s, st):
    if adopt_check(s, st):
        return
    case = f'{s}__c4'
    logf = R / f'logs/check_{case}.log'
    with open(ROOT / logf, 'w') as f:
        rc = subprocess.run([PY, 'experiments/bem_on_baseline_data/csi_forward_check.py', '--out', str(R / 'adapter_checks'),
                             '--cases', case], stdout=f, stderr=subprocess.STDOUT).returncode
    js = ROOT / R / 'adapter_checks' / f'{case}.json'
    result = 'error'
    if rc == 0 and js.exists():
        d = json.loads(js.read_text())
        sm = d['summary']
        per = {}
        for r in d['mismatch']['per_frequency']:
            per[r['frequency_ghz']] = max(per.get(r['frequency_ghz'], 0), r['relative_mismatch'])
        st[s]['mismatch_pct'] = {str(k): round(100 * v, 4) for k, v in per.items()}
        st[s]['sha256'] = d['mismatch']['source']['sha256']
        result = 'pass' if (sm['adapter_checks_pass'] and sm['one_percent_rule']) else 'fail'
    st[s]['check'] = result
    save(st)
    git([R / 'adapter_checks' / f'{case}.json', logf], f'CSI five-frequency pass: {s} 1% check {result}')
    if result != 'pass':
        alert(f'{s} check {result} (exit {rc}); shape not fitted')
    else:
        log(f'{s} check pass {st[s]["mismatch_pct"]}')


def attempt_with_metrics(s, dev):
    base = ROOT / R / f'{s}__c4' / dev
    for a in sorted(base.glob('attempt_*')) if base.exists() else []:
        if (a / 'metrics.json').exists():
            return a
    return None


def launch(s, dev, st, procs):
    case = f'{s}__c4'
    (ROOT / R / 'logs').mkdir(exist_ok=True)
    logf = ROOT / R / 'logs' / f'{case}_{"cuda" if dev == "gpu" else "cpu"}.log'
    env = dict(os.environ)
    argdev = 'cuda' if dev == 'gpu' else 'cpu'
    if dev == 'cpu':
        env['CUDA_VISIBLE_DEVICES'] = ''
    f = open(logf, 'w')
    p = subprocess.Popen([PY, 'experiments/bem_on_baseline_data/csi_fit.py', '--case', case, '--device', argdev],
                         stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, start_new_session=True)
    procs[(s, dev)] = (p, logf)
    st[s][dev] = 'running'
    save(st)
    log(f'launched {dev} fit {case} pid {p.pid}')


def finish(s, dev, p, logf, st):
    case = f'{s}__c4'
    ddir = 'cuda' if dev == 'gpu' else 'cpu'
    time.sleep(2)
    a = attempt_with_metrics(s, ddir)
    text = logf.read_text() if logf.exists() else ''
    if a is None and 'to start' in text and p.returncode != 0:
        log(f'{case} {dev}: wrapper refused to start (memory); will retry')
        st[s][dev] = 'none'; save(st); return
    if a is not None:
        m = json.loads((a / 'metrics.json').read_text())
        st[s][dev] = 'done'
        st[s][dev + '_outcome'] = m.get('outcome') or m.get('status')
        log(f'{case} {dev} done: {st[s][dev + "_outcome"]}')
        if dev == 'gpu':
            alert(f'{case} gpu fit finished: {st[s][dev + "_outcome"]}')
    else:
        st[s][dev] = 'crashed'
        alert(f'{case} {dev} fit ended without metrics.json (exit {p.returncode}); kept, not rerun')
    save(st)
    git([R / f'{s}__c4' / ddir, R / 'logs' / logf.name], f'CSI five-frequency pass: {case} {dev} fit ({st[s][dev]})')


def main():
    st = load()
    procs = {}
    log(f'waiter start pid {os.getpid()}')
    n_ok = 0
    while True:
        # 1. checks as tables freeze
        for s in SHAPES:
            if st[s]['check'] == 'pending' and table_ready(s):
                run_check(s, st)
        # 2. completion of my own launched fits
        for key, (p, logf) in list(procs.items()):
            if p.poll() is not None:
                finish(key[0], key[1], p, logf, st)
                del procs[key]
        # 3. launches
        gpu_over = all(st[s]['check'] in ('fail', 'error') or st[s]['gpu'] in ('done', 'crashed') for s in SHAPES)
        cpu_over = all(st[s]['check'] in ('fail', 'error') or st[s]['gpu'] != 'done' or st[s]['cpu'] in ('done', 'crashed')
                       for s in SHAPES)
        if gpu_over and cpu_over and all(st[s]['check'] != 'pending' for s in SHAPES):
            log('all work finished'); alert('waiter finished: all checks, GPU fits and CPU cross-checks are over'); break
        launched = True
        while launched:
            launched = False
            running_gpu = [k for k in procs if k[1] == 'gpu']
            running_cpu = [k for k in procs if k[1] == 'cpu']
            if not gpu_over:
                cand = next((s for s in SHAPES if st[s]['check'] == 'pass' and st[s]['gpu'] == 'none'), None)
                dev = 'gpu'
            elif not running_gpu and not running_cpu:
                cand = next((s for s in SHAPES if st[s]['gpu'] == 'done' and st[s]['cpu'] == 'none'), None)
                dev = 'cpu'
            else:
                cand = None
            if cand:
                ok, why = slot_free()
                if ok:
                    launch(cand, dev, st, procs)
                    time.sleep(20)       # let the new worker show up in the process list and its memory settle
                    launched = True
                else:
                    n_ok += 1
                    if n_ok % 20 == 1:
                        log(f'waiting for slot for {cand} {dev}: {why}')
        time.sleep(POLL)


if __name__ == '__main__':
    main()
