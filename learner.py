import time, sys
import gd_run as g

def attempt(jumps, duration=15.0, poll=0.12):
    H = g.find_gl(); g.top(H); time.sleep(0.15)
    g.tap(g.VK_R); time.sleep(0.05)
    t0 = time.time()
    fired = [False]*len(jumps)
    started = False
    maxT = 0.0; lastT = None; deathT = None; startAttempt = None; lastX = None
    nextp = 0.0
    while time.time() - t0 < duration:
        el = time.time() - t0
        if el >= nextp:
            g.top(H)
            st = g.read_state(g.grab())
            nextp = el + poll
            if not started:
                g.tap(g.VK_SPACE); started = True; startAttempt = st["attempt"]
            t = st["time"]
            if t is not None:
                if startAttempt is None:
                    startAttempt = st["attempt"]
                if lastT is not None and (t < lastT - 0.3 or (st["attempt"] is not None and startAttempt is not None and st["attempt"] > startAttempt)):
                    deathT = lastT; break
                if t > maxT:
                    maxT = t
                lastT = t
                lastX = st["x"]
        for i, tg in enumerate(jumps):
            if not fired[i] and lastT is not None and lastT >= tg:
                g.tap(g.VK_SPACE); fired[i] = True
        time.sleep(0.008)
    return maxT, deathT, lastX

if __name__ == "__main__":
    jumps = [0.0]
    best = 0.0
    for it in range(int(sys.argv[1]) if len(sys.argv) > 1 else 15):
        mt, dt, x = attempt(jumps)
        print(f"iter {it:2d}  jumps={jumps}  maxTime={mt:.2f}  deathT={dt}  deathX={x}")
        if dt is None:
            print("  -> survived full window (no death detected)")
            break
        if mt > best:
            best = mt
        nt = max(0.05, (dt if dt is not None else mt) - 0.12)
        if any(abs(nt - j) < 0.15 for j in jumps):
            nt = max(0.05, (dt if dt is not None else mt) - 0.22)
        if any(abs(nt - j) < 0.12 for j in jumps):
            print("  -> cannot place new jump, stopping")
            break
        jumps.append(round(nt, 2)); jumps.sort()
