"""Class power sounds: the Cleric's heal, the Warrior's doubled damage, the Paladin's shield,
and the dull "no effect" when the enemy is immune to a power.

Everything here is acoustic: real instruments recorded in the General MIDI banks
(``sf.py``: harp, celesta, glockenspiel, choir and humming voices, French horns, a brass
section, timpani, recorder, fiddle, cello, a tubular bell, a nylon-strung guitar played
like a lute) and real-world things modelled from their physics (sword steel, an oak
table, pewter, a wooden shield, leather, a door, stone, the bubbles in a potion, a
candle's wick). Nothing is 8-bit and no tone is a bare oscillator. Five candidates per
event, each a different character: the action itself (foley), a soft one for long
sessions or a wooden tavern one, a courtly instrumental one, and a grand or mysterious
one. The owner's picks keep their ids and names (potion_bubbles, power_surge, fizzle),
remade acoustically in the same spirit.

A power plays 0.18 s after the cards and 0.24 s before the hit, so each one makes its
point in its first quarter of a second and then gets out of the way: tails are short,
damped by a hand on the strings (``_damp``) or by the room. A phone's speaker plays
little below about 200 Hz, so every low sound also has body between 300 Hz and 3 kHz.
Tonal parts are in D: D major pentatonic (D E F# A B) for the bright powers, D dorian
(with F natural) for the glum "immune" sounds.

Recordings: rendered once per sample and cached (``_bank``); each instrument is rendered
on its own so its attack latency can be cut separately (``sf.onset``), and every sound
starts at once. Each instrument comes from the bank that plays it better or in tune
(the Fluid recorder's D5 is 24 cents sharp, both choirs' D4 sit flat: MuseScore's,
bent back into tune, is used). Physical models (all private here):
  _modal / _reson    struck objects: resonators (one per mode) driven by a short pulse
                     whose width is the hardness of what strikes (wood, steel, glass)
  _bubble            a bubble in a liquid (Minnaert resonance, van den Doel's damping)
  _crackle           sparse tiny impacts (a wick sputtering, grit trickling)
  _leather           stick-slip: a leather strap creaking
  _room              a small stone room: a noise impulse response whose highs die first
  _tame              rounds off only the first instant of a blow that would otherwise
                     push the master's limiter
"""
from __future__ import annotations

import dataclasses
import functools
import math
from typing import Sequence, Tuple

import numpy as np
from scipy import signal

import sf
import synth as A
from catalog import EVENT_BY_ID, Candidate
from sf import DRUM, GM, Note

SR = A.SR
TAU = 2 * math.pi


def N(name: str) -> float:
    return A.note_hz(name)


# ============================================================================= basics
def _n(d: float) -> int:
    return A.n_of(d)


def _t(d: float) -> np.ndarray:
    return A.seconds(d)


def _buf(d: float) -> np.ndarray:
    return np.zeros(_n(d))


def _len(x: np.ndarray, d: float) -> np.ndarray:
    n = _n(d)
    return x[:n].copy() if len(x) >= n else np.concatenate([x, np.zeros(n - len(x))])


def _norm(x: np.ndarray) -> np.ndarray:
    p = float(np.max(np.abs(x))) if len(x) else 0.0
    return x / p if p > 0 else x


def _en(x: np.ndarray) -> np.ndarray:
    """Unit energy, so mixing gains set each layer's share of the energy."""
    e = math.sqrt(float(np.sum(x ** 2)) / SR * 1000.0)
    return x / e if e > 0 else x


def _tail(x: np.ndarray, sec: float) -> np.ndarray:
    """A raised-cosine fade over the last ``sec`` seconds."""
    k = min(len(x), max(2, _n(sec)))
    y = x.copy()
    y[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, k))
    return y


def _rise(n: int, attack: float) -> np.ndarray:
    e = np.ones(n)
    k = min(n, max(2, _n(attack)))
    e[:k] = 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    return e


def _mix(parts, d: float) -> np.ndarray:
    """[(sound, at seconds, gain), ...] mixed into one buffer ``d`` seconds long."""
    buf = _buf(d)
    for snd, at, g in parts:
        buf = A.mix_at(buf, snd, at, g)
    return buf[:_n(d)]


def _noise(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(n)


def _env(d: float, tau: float, attack: float = 0.0005) -> np.ndarray:
    n = _n(d)
    return np.exp(-_t(d) / max(tau, 1e-5)) * _rise(n, attack)


def _loud(x: np.ndarray) -> float:
    return A._rms_db(x)


# ============================================================================= recordings
@functools.lru_cache(maxsize=None)
def _bank_cached(key: tuple, seconds: float, bank: str) -> np.ndarray:
    return sf.render([Note(*k) for k in key], seconds, bank=bank)


def _bank(notes: Sequence[Note], seconds: float, bank: str = "fluid", cut: bool = True) -> np.ndarray:
    """Render ``notes`` from a bank (cached), the bank's attack latency cut so the first
    note sounds at once."""
    key = tuple(dataclasses.astuple(n) for n in notes)
    x = _bank_cached(key, round(float(seconds), 4), bank).copy()
    return x[sf.onset(x, -50.0):] if cut else x


def _one(program: int, pitch, dur: float, vel: int, seconds: float, bank: str = "fluid", **kw) -> np.ndarray:
    return _bank([Note(program, pitch, 0.0, dur, vel=vel, **kw)], seconds, bank)


def _damp(x: np.ndarray, hold: float, tau: float, total: float = 0.0) -> np.ndarray:
    """A hand on the strings: full level for ``hold`` seconds, then an exponential fall
    (time constant ``tau``) to zero by ``total`` (default 7 time constants on)."""
    total = total or hold + 7 * tau
    n = min(len(x), _n(total))
    t = np.arange(n) / SR
    env = np.where(t < hold, 1.0, np.exp(-(t - hold) / max(tau, 1e-4)))
    return _tail(x[:n] * env, min(0.05, total * 0.2))


# ============================================================================= physics
def _reson(x: np.ndarray, f: float, t60: float) -> np.ndarray:
    """A two-pole resonator at ``f`` ringing for ``t60`` seconds (to -60 dB)."""
    w = TAU * min(f, SR * 0.45) / SR
    r = 10 ** (-3.0 / (max(t60, 1e-4) * SR))
    return signal.lfilter([math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], x)


def _strike(width: float, seed: int = 0, rough: float = 0.0) -> np.ndarray:
    """What strikes: a Hann pulse ``width`` seconds wide (its spectrum falls away above
    about 1 / width), roughened by a little noise for a gritty contact."""
    k = max(3, _n(width))
    w = np.hanning(k + 2)[1:-1]
    if rough:
        w = w * (1 + rough * np.random.default_rng(seed).uniform(-1, 1, k))
    return w / np.sum(np.abs(w))


def _modal(d: float, modes: Sequence[Tuple[float, float, float]], width: float,
           hits: Sequence[Tuple[float, float]] = ((0.0, 1.0),), seed: int = 0, rough: float = 0.0,
           split: float = 0.0) -> np.ndarray:
    """An object with modes [(Hz, t60, gain), ...] struck at ``hits`` [(seconds, amp)].
    ``split`` turns each mode into a slightly detuned pair (no real object is perfectly
    symmetric: metal and glass shimmer as the pair beats)."""
    n = _n(d)
    exc = np.zeros(n)
    for at, amp in hits:
        i = _n(at)
        if i < n:
            exc[i] += amp
    exc = np.convolve(exc, _strike(width, seed, rough))[:n]
    rng = np.random.default_rng(seed + 7)
    y = np.zeros(n)
    for f, t60, g in modes:
        if f >= SR * 0.45 or g == 0:
            continue
        if split:
            dv = f * split * rng.uniform(0.5, 1.0)
            y += g * 0.5 * (_reson(exc, f - dv / 2, t60) + _reson(exc, f + dv / 2, t60))
        else:
            y += g * _reson(exc, f, t60)
    return y


def _click(d: float, lo: float, hi: float, tau: float, seed: int) -> np.ndarray:
    """The contact noise of an impact."""
    return A.bandpass(_noise(_n(d), seed) * _env(d, tau, 0.0002), lo, hi, 2)


def _crackle(d: float, rate: Sequence[float], band: Tuple[float, float], seed: int, ring: float = 0.004,
             spread: float = 1.0) -> np.ndarray:
    """Sparse tiny impacts (Poisson, at ``rate`` per second, which may change over time
    as (start, end)), each a short ring at a random pitch inside ``band`` with a
    heavy-tailed spread of strengths."""
    rng = np.random.default_rng(seed)
    n = _n(d)
    y = np.zeros(n)
    t = 0.0
    r0, r1 = rate
    while True:
        r = r0 + (r1 - r0) * min(1.0, t / d)
        if r <= 0:
            break
        t += rng.exponential(1.0 / r)
        if t >= d:
            break
        f = math.exp(rng.uniform(math.log(band[0]), math.log(band[1])))
        amp = min(1.0, rng.pareto(2.0) * 0.4 + 0.1) ** spread
        m = _n(ring * 6)
        imp = np.zeros(m)
        imp[0] = 1.0
        s = _reson(np.convolve(imp, _strike(0.0003))[:m], f, ring)
        i = _n(t)
        k = min(m, n - i)
        y[i:i + k] += amp * s[:k] * (1 if rng.random() < 0.5 else -1)
    return y


def _bubble(f0: float, d: float, xi: float = 0.1, damp: float = 1.0) -> np.ndarray:
    """A bubble in water (Minnaert): a damped sine at f0 whose pitch rises as the bubble
    nears the surface; damping after van den Doel (0.13 f + 0.0072 f^1.5 per second),
    so a 1 kHz bubble is over in about 20 ms, as a real one is."""
    dm = (0.13 * f0 + 0.0072 * f0 ** 1.5) * damp
    n = _n(d)
    t = np.arange(n) / SR
    f = f0 * (1 + xi * dm * t)
    y = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-dm * t)
    return y * _rise(n, 0.0006)


@functools.lru_cache(maxsize=None)
def _ir(rt60: float, seed: int, bright: float) -> np.ndarray:
    """A small stone room's impulse response: a few early reflections, then dense noise
    whose high frequencies die about twice as fast as its lows."""
    n = _n(rt60 * 1.2)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    split = 1200.0 * bright
    lo = A.lowpass(w, split, 2) * np.exp(-6.9078 * t / rt60)
    hi = A.highpass(w, split, 2) * np.exp(-6.9078 * t / (rt60 * 0.45))
    ir = lo + 0.7 * A.lowpass(hi, 7000 * bright, 2)
    ir *= np.clip((t - 0.008) / 0.012, 0, 1)
    for k in range(7):
        i = _n(rng.uniform(0.004, 0.028))
        ir[i] += rng.uniform(0.25, 0.6) * (1 if k % 2 else -1) * math.sqrt(np.mean(ir[:_n(0.05)] ** 2)) * 30
    return ir / math.sqrt(float(np.sum(ir ** 2)))


def _room(x: np.ndarray, rt60: float = 0.6, wet: float = 0.2, seed: int = 5, bright: float = 1.0) -> np.ndarray:
    """``x`` heard in a small stone room (the dry sound plus ``wet`` of the room, by
    energy); the result is as long as ``x`` (give it room to ring)."""
    ir = _ir(round(rt60, 3), seed, round(bright, 3))
    w = signal.fftconvolve(x, ir)[:len(x)]
    return x + wet * w * (math.sqrt(np.sum(x ** 2)) / (math.sqrt(np.sum(w ** 2)) + 1e-12))


# ============================================================================= finishing
def _softlimit(x: np.ndarray, ceil: float, look: float = 0.002, release: float = 0.03) -> np.ndarray:
    """A peak limiter whose gain never steps: the gain each sample needs, held over the
    look-ahead on both sides, recovered with a one-pole release and then smoothed by a
    Hann window no wider than the hold, so it is always at or under what is needed and
    turns down over a couple of milliseconds instead of clicking."""
    from scipy.ndimage import minimum_filter1d
    w = max(2, _n(look))
    want = np.minimum(1.0, ceil / np.maximum(np.abs(x), 1e-12))
    g = minimum_filter1d(want, size=2 * w + 1)
    a = math.exp(-1.0 / max(1, _n(release)))
    gl = g.tolist()
    out = [1.0] * len(gl)
    prev = 1.0
    for i, v in enumerate(gl):
        prev = v if v < prev else prev + (1 - a) * (v - prev)
        out[i] = prev
    g = np.asarray(out)
    k = np.hanning(2 * w + 1)
    g = np.convolve(np.pad(g, (w, w), mode="edge"), k / k.sum(), mode="valid")
    return x * g


def _tame(x: np.ndarray, loudness_db: float, margin_db: float = 1.0, max_shave_db: float = 4.0) -> np.ndarray:
    """If the first instant of an attack would rise above the master's ceiling once the
    sound is brought to its loudness, round off just that instant (``_softlimit``, a
    12 ms release), by ``max_shave_db`` at most. An impact's loudness lives in its first
    few milliseconds, so shaving more would only flatten the blow against its own tail;
    whatever remains is left to the master's gentle limiter."""
    allowed = -1.0 - margin_db - loudness_db
    y = x
    shaved = 0.0
    for _ in range(6):
        pk = 20 * math.log10(float(np.max(np.abs(y))) + 1e-12)
        crest = pk - _loud(y)
        if crest <= allowed or shaved >= max_shave_db:
            break
        cut = min(crest - allowed + 0.3, max_shave_db - shaved)
        y = _softlimit(y, 10 ** ((pk - cut) / 20.0), release=0.012)
        shaved += cut
    return y


def _finish(x: np.ndarray, event: str, fade: float = 0.2, hp: float = 45.0, lp: float = 9000.0,
            shave: float = 4.0) -> np.ndarray:
    """Finish a sound for its event: no rumble below ``hp``, nothing harsh above ``lp``,
    inside the event's length with a natural fade, its first peak tamed (by ``shave``
    dB at most: more only where that peak is a brief contact click, not the blow)."""
    ev = EVENT_BY_ID[event]
    y = A.highpass(x, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 2)
    nmax = _n(ev.max_seconds - 0.03)
    if len(y) > nmax:
        y = y[:nmax]
    y = _tail(y, min(fade, len(y) / SR * 0.5))
    return _tame(y, ev.loudness_db, max_shave_db=shave)


# ============================================================================= heal (Cleric)
def _heal_bubbles() -> np.ndarray:
    """A potion: a cork eased out of a small glass bottle, the potion bubbling up (real
    bubble sizes, not tuned: the big ones first, then smaller and quicker ones, rising
    in pitch), a fine fizz, and a tiny clink of the glass, with a celesta's soft D and A
    sounding in it."""
    d = 1.5
    rng = np.random.default_rng(801)
    parts = []
    # the cork: the pop's click, then the neck's air resonance rising as air rushes in
    pop = _click(0.02, 400, 4000, 0.0015, 802)
    neck = _bubble(560.0, 0.12, xi=0.35, damp=0.7)
    parts += [(_en(pop), 0.0, 0.5), (_en(neck), 0.0005, 0.9)]
    # bubbles: Poisson, sizes log-normal around a centre that rises (smaller bubbles)
    t = 0.03
    while t < 0.7:
        u = t / 0.7
        centre = 600 * (2200 / 600) ** u
        f = centre * math.exp(rng.normal(0, 0.28))
        amp = (600.0 / f) ** 0.6 * rng.uniform(0.4, 1.0) * (1.0 - 0.6 * u)
        parts.append((_bubble(f, 0.08, xi=rng.uniform(0.08, 0.14)), t, 0.32 * amp))
        t += rng.exponential(0.015 + 0.035 * u)
    # the fizz: many tiny bubbles at the surface, faint
    fizz = np.zeros(_n(1.0))
    tt = 0.06
    while tt < 0.8:
        f = rng.uniform(2600, 5200)
        fizz = A.mix_at(fizz, _bubble(f, 0.02, 0.1), tt, rng.uniform(0.2, 1.0))
        tt += rng.exponential(0.006)
    fizz = fizz[:_n(1.0)] * np.clip(_t(1.0) / 0.2, 0, 1) * np.exp(-np.clip(_t(1.0) - 0.45, 0, None) / 0.12)
    parts.append((_en(fizz), 0.0, 0.25))
    # the glass: a vial's modes (1, 2.32, 4.25, 6.63) on D6, a light tap
    f = N("D6")
    glass = _modal(0.9, [(f, 0.8, 1.0), (f * 2.32, 0.4, 0.35), (f * 4.25, 0.2, 0.12), (f * 6.63, 0.12, 0.05)],
                   0.00025, seed=803, split=0.0015)
    parts.append((_en(glass), 0.62, 0.5))
    cel = _damp(_one(GM["celesta"], "D6", 0.3, 70, 1.6, "musescore"), 0.4, 0.12)
    cel2 = _damp(_one(GM["celesta"], "A5", 0.3, 55, 1.6, "musescore"), 0.4, 0.12)
    parts += [(_en(cel), 0.625, 0.38), (_en(cel2), 0.66, 0.22)]
    x = _mix(parts, d + 0.2)
    x = _room(x, 0.5, 0.18, 11)
    return _finish(x, "power_heal", 0.35, hp=120, lp=8000, shave=8.0)


def _heal_harp() -> np.ndarray:
    """A real harp sweeps up a D major chord from D3 to D6 and is left to ring, then a
    hand settles on the strings."""
    seq = ["D3", "A3", "D4", "F#4", "A4", "D5", "F#5", "A5", "D6"]
    notes = [Note(GM["harp"], nm, 0.048 * k, 1.2, vel=72 + 3 * k) for k, nm in enumerate(seq)]
    x = _bank(notes, 2.4, "musescore")
    x = _damp(x, 0.75, 0.18, 1.58)
    x = _room(_len(x, 1.7), 0.7, 0.16, 12)
    return _finish(x, "power_heal", 0.3, hp=60)


def _heal_glow() -> np.ndarray:
    """A soft harp note on D, then a quiet bowed chord (D, A, F#) swells warmly beneath
    it and fades, with one faint celesta A on top."""
    harp = _one(GM["harp"], "D4", 0.8, 70, 2.0, "musescore")
    strings = [Note(GM["strings"], nm, 0.0, 0.32, vel=v, swell=(80, 105)) for nm, v in
               (("D3", 70), ("A3", 64), ("F#4", 58), ("D4", 60))]
    st = _bank(strings, 2.0, "musescore")
    st = st * np.minimum(1.0, _t(len(st) / SR) / 0.2)
    cel = _one(GM["celesta"], "A5", 0.3, 50, 1.6, "musescore")
    x = _mix([(_en(harp), 0.0, 0.8), (_en(st), 0.02, 1.0), (_en(cel), 0.16, 0.25)], 1.6)
    x = _damp(x, 0.6, 0.2, 1.58)
    x = _room(x, 0.8, 0.2, 13)
    return _finish(x, "power_heal", 0.3, hp=60)


def _heal_holy() -> np.ndarray:
    """A choir sings out a D major chord while a celesta climbs bright and quick above it
    and a harp sounds the low D."""
    # the MuseScore choir's D4 sample sits 24 cents flat: a steady bend puts it in tune
    choir = [Note(GM["choir"], "D4", 0.0, 0.5, vel=82, bend=(0.24, 0.24))] + \
            [Note(GM["choir"], nm, 0.0, 0.5, vel=v) for nm, v in (("A4", 78), ("D5", 76), ("F#5", 70))]
    ch = _bank(choir, 2.2, "musescore")
    run = ["A5", "B5", "D6", "E6", "F#6", "A6"]
    cel = _bank([Note(GM["celesta"], nm, 0.05 * k, 0.4, vel=70 + 5 * k) for k, nm in enumerate(run)], 2.0,
                "musescore")
    harp = _one(GM["harp"], "D3", 0.8, 85, 2.0, "musescore")
    x = _mix([(_en(ch), 0.0, 1.0), (_en(cel), 0.0, 0.55), (_en(harp), 0.0, 0.35)], 1.7)
    x = _damp(x, 0.55, 0.16, 1.58)
    x = _room(x, 1.0, 0.26, 14)
    return _finish(x, "power_heal", 0.3, hp=70)


def _heal_tune() -> np.ndarray:
    """A recorder plays a quick rising D-F#-A and holds a high D, over a nylon-strung lute
    strummed once on a D chord."""
    rec = [Note(GM["recorder"], nm, at, dur, vel=v) for nm, at, dur, v in
           (("D5", 0.0, 0.075, 92), ("F#5", 0.085, 0.075, 92), ("A5", 0.17, 0.075, 94))] + \
          [Note(GM["recorder"], "D6", 0.255, 0.4, vel=96, swell=(120, 60))]
    r = _bank(rec, 1.8, "musescore")      # Fluid's recorder D5 is 24 cents sharp
    strum = [Note(GM["nylon_guitar"], nm, 0.012 * k, 0.9, vel=78 - 2 * k) for k, nm in
             enumerate(["D3", "A3", "D4", "F#4", "A4"])]
    lute = _bank(strum, 2.0, "fluid")
    lute = _damp(lute, 0.75, 0.15)
    x = _mix([(_en(r), 0.0, 1.0), (_en(lute), 0.0, 0.55)], 1.6)
    x = _room(x, 0.6, 0.18, 15)
    return _finish(x, "power_heal", 0.3, hp=70)


# ============================================================================= double (Warrior)
def _blade(f0: float, d: float, seed: int, power: float = 1.0, scrape: float = 0.0) -> np.ndarray:
    """A sword blow on a blade: two steel blades' bending modes (a free bar's 1, 2.76,
    5.40, 8.93, 13.3 times the lowest; each a slowly beating pair), struck by a hard
    gritty contact, with an optional scrape of edge along edge (the "shing": friction
    noise driving the same modes) and the dull knock of the hilts in the hands."""
    ratios = (1.0, 2.756, 5.404, 8.933, 13.34)
    modes = []
    for k, (r, g, T) in enumerate(zip(ratios, (0.7, 1.0, 0.8, 0.5, 0.25), (0.9, 0.75, 0.55, 0.35, 0.2))):
        modes.append((f0 * r, T * power, g))
        modes.append((f0 * 1.137 * r, T * 0.8 * power, g * 0.6))       # the other blade
    y = _modal(d, modes, 0.00015, seed=seed, rough=0.6, split=0.002)
    if scrape:
        m = _n(0.07)
        tt = np.arange(m) / SR
        fr = np.sin(np.pi * tt / 0.07) ** 2 * (1 + 0.5 * _norm(A.lowpass(_noise(m, seed + 3), 120, 1)))
        exc = A.highpass(_noise(m, seed + 4), 1500, 2) * fr * 0.004 * scrape
        y = y + _len(sum(g * _reson(np.concatenate([exc, np.zeros(_n(d) - m)]), f, T * 0.5)
                         for f, T, g in modes), d)
    crack = _click(0.03, 1500, 7000, 0.0012, seed + 1)
    hilt = A.lowpass(_noise(_n(0.06), seed + 2), 700, 2) * _env(0.06, 0.012, 0.001)
    hilt = _reson(hilt, 210, 0.05) + 0.5 * hilt
    y = _en(y) + 0.25 * _len(_en(crack), d) + 0.35 * power * _len(_en(hilt), d)
    return y


def _double_twin() -> np.ndarray:
    """Two sword blows in quick succession: a ringing clash, the swish of the second
    swing, and a harder clash with a short scrape of steel on steel."""
    d = 1.15
    sw_d = 0.09
    ts = _t(sw_d)
    swish = A.bandpass(_noise(_n(sw_d), 205), 500, 2500, 2) * np.sin(np.pi * ts / sw_d) ** 3
    x = _mix([(_blade(520.0, 1.0, 201, 0.8), 0.0, 0.8),
              (_en(swish), 0.05, 0.25),
              (_blade(600.0, 1.0, 211, 1.1, scrape=1.0), 0.13, 1.0)], d + 0.3)
    x = _room(x, 0.6, 0.15, 21)
    return _finish(x, "power_double", 0.4, hp=80)


def _double_surge() -> np.ndarray:
    """Power gathers in a quick rush (a field drum's roll swelling over a timpani roll)
    and bursts in a bright double strike: brass, timpani and glockenspiel cut off short,
    then the same an octave higher with a cymbal, soon damped. (No harp sweep: the
    owner's hit, arcane_bolt, opens with one a quarter of a second later.)"""
    roll = [Note(DRUM, 50, 0.022 * k, 0.05, vel=80 + 8 * k, kit="orchestra") for k in range(6)]
    tr = _bank(roll, 1.0, "fluid")
    strokes = [Note(DRUM, 38, 0.018 * k, 0.03, vel=44 + 10 * k, kit="orchestra") for k in range(7)]
    gliss = A.lowpass(_bank(strokes, 1.0, "musescore"), 6500, 2)     # the drum's roll (kept the old name)
    gliss = _damp(gliss, 0.13, 0.03)
    hit1 = _bank([Note(GM["brass"], nm, 0.0, 0.08, vel=110) for nm in ("D4", "A4", "D5")], 1.4, "fluid")
    hit2 = _bank([Note(GM["brass"], nm, 0.0, 0.12, vel=118) for nm in ("D5", "A5", "D6")], 1.4, "fluid")
    t1 = _bank([Note(DRUM, 50, 0.0, 0.2, vel=120, kit="orchestra")], 1.4, "fluid")
    t2 = _bank([Note(DRUM, 45, 0.0, 0.2, vel=127, kit="orchestra")], 1.4, "fluid")
    cym = _bank([Note(DRUM, 57, 0.0, 0.2, vel=100, kit="orchestra")], 1.6, "fluid")
    gl1 = _one(GM["glockenspiel"], "D5", 0.2, 100, 1.4, "musescore")
    gl2 = _one(GM["glockenspiel"], "D6", 0.2, 110, 1.4, "musescore")
    first = _mix([(_en(hit1), 0.0, 0.8), (_en(t1), 0.0, 0.55), (_en(gl1), 0.0, 0.3)], 0.4)
    first = _damp(first, 0.06, 0.02, 0.2)
    second = _mix([(_en(hit2), 0.0, 0.9), (_en(t2), 0.0, 0.6), (_en(gl2), 0.0, 0.35), (_en(cym), 0.0, 0.2)], 1.2)
    second = _damp(second, 0.22, 0.12, 0.98)
    h1, h2 = 0.12, 0.22
    x = _mix([(_en(tr), 0.0, 0.5), (_en(gliss), 0.0, 0.45), (_en(first), h1, 0.9), (_en(second), h2, 1.25)], 1.4)
    x = _room(x, 0.8, 0.2, 22)
    return _finish(x, "power_double", 0.3, hp=70)


def _double_drums() -> np.ndarray:
    """Two war kettledrums (real timpani, with a deep drum under them for weight): a
    strong stroke on D, a grace stroke and a bigger, lower stroke on A."""
    t1 = _bank([Note(DRUM, 50, 0.0, 0.3, vel=110, kit="orchestra")], 1.4, "fluid")
    grace = _bank([Note(DRUM, 50, 0.0, 0.1, vel=60, kit="orchestra")], 1.0, "fluid")
    t2 = _bank([Note(DRUM, 45, 0.0, 0.3, vel=127, kit="orchestra")], 1.4, "musescore")
    deep = _one(GM["taiko"], "A3", 0.3, 120, 1.4, "fluid")
    x = _mix([(_en(t1), 0.0, 0.8), (_en(deep), 0.0, 0.25),
              (_en(grace), 0.16, 0.25),
              (_en(t2), 0.2, 1.0), (_en(deep), 0.2, 0.35)], 1.4)
    x = A.peak_eq(x, 520, 4.0, 0.9)
    x = A.peak_eq(x, 1100, 3.0, 1.0)
    x = _damp(x, 0.45, 0.13, 1.17)
    x = _room(x, 0.8, 0.2, 23)
    return _finish(x, "power_double", 0.3, hp=55)


def _double_horn() -> np.ndarray:
    """Two French horns call out together, a short A and a long D, the second horn an
    octave below the first."""
    hi = [Note(GM["french_horn"], "A4", 0.0, 0.12, vel=110), Note(GM["french_horn"], "D5", 0.15, 0.36, vel=118,
                                                                   swell=(127, 80))]
    lo = [Note(GM["french_horn"], "A3", 0.0, 0.12, vel=100), Note(GM["french_horn"], "D4", 0.15, 0.36, vel=108,
                                                                   swell=(127, 80))]
    a = _bank(hi, 1.6, "fluid")
    b = _bank(lo, 1.6, "musescore")
    x = _mix([(_en(a), 0.0, 1.0), (_en(b), 0.004, 0.75)], 1.4)
    x = _room(x, 1.0, 0.24, 24)
    return _finish(x, "power_double", 0.3, hp=70)


def _table(d: float, hits, seed: int) -> np.ndarray:
    """A heavy oak tavern table struck by a fist: the top's low, well-damped bending
    modes, the knuckles' knock on the wood and the legs' rattle on the stone floor."""
    top = [(98, 0.16, 0.6), (151, 0.14, 0.7), (233, 0.12, 0.8), (322, 0.1, 0.9), (447, 0.08, 0.85),
           (611, 0.06, 0.7), (838, 0.045, 0.5), (1130, 0.03, 0.3), (1560, 0.02, 0.15)]
    y = _modal(d, top, 0.004, hits, seed=seed, rough=0.3)
    knock = _modal(d, [(N("D5"), 0.03, 1.0), (N("A5") * 1.07, 0.02, 0.5), (2100, 0.012, 0.3)], 0.0012, hits,
                   seed=seed + 1)
    return A.peak_eq(_en(y) + 0.45 * _en(knock), 500, 4.0, 0.8)


def _pewter(f0: float, d: float, seed: int, t60: float = 0.25) -> np.ndarray:
    """A pewter tankard jumping on the table: a soft metal's few short, dull modes."""
    modes = [(f0, t60, 1.0), (f0 * 2.13, t60 * 0.7, 0.7), (f0 * 3.41, t60 * 0.5, 0.45), (f0 * 4.92, t60 * 0.35, 0.2)]
    return _modal(d, modes, 0.0004, seed=seed, split=0.004)


def _double_table() -> np.ndarray:
    """A fist pounds the tavern table twice, bang then BANG, and the pewter tankards on
    it jump and clatter."""
    d = 1.1
    hits = [(0.0, 0.7), (0.16, 1.0)]
    x = _table(d, hits, 301)
    rng = np.random.default_rng(302)
    parts = [(x, 0.0, 1.0)]
    for at, a in hits:
        for j in range(3):
            f0 = N(["A4", "D5", "F#5"][j]) * rng.uniform(0.97, 1.03)
            parts.append((_en(_pewter(f0, 0.5, 303 + j + int(at * 100))), at + 0.012 + 0.03 * j + rng.uniform(0, 0.01),
                          0.22 * a * rng.uniform(0.6, 1.0)))
            parts.append((_en(_pewter(f0, 0.5, 313 + j)), at + 0.07 + 0.035 * j, 0.09 * a))
    x = _mix(parts, d + 0.2)
    x = _room(x, 0.6, 0.18, 25)
    return _finish(x, "power_double", 0.3, hp=60)


# ============================================================================= shield (Paladin)
def _shield_bash() -> np.ndarray:
    """A blow lands on a round wooden shield: the planks thud, the iron boss at its
    centre clanks, and the iron rim rattles once against the wood."""
    d = 1.0
    planks = [(162, 0.13, 1.0), (241, 0.12, 0.95), (356, 0.1, 0.85), (497, 0.085, 0.7), (672, 0.07, 0.55),
              (883, 0.055, 0.4), (1150, 0.04, 0.25), (1490, 0.03, 0.14)]
    wood = _modal(d, planks, 0.0025, seed=551, rough=0.4)
    boss_f = N("A5")
    boss = _modal(d, [(boss_f * r, T, g) for r, T, g in
                      ((1.0, 0.35, 1.0), (1.48, 0.28, 0.7), (2.13, 0.2, 0.5), (2.71, 0.15, 0.3), (3.36, 0.1, 0.2))],
                  0.0004, seed=552, split=0.003)
    rattle = _modal(0.3, [(2350, 0.05, 1.0), (3410, 0.04, 0.6), (1720, 0.06, 0.5)], 0.0002,
                    hits=((0.0, 1.0), (0.021, 0.5), (0.036, 0.3)), seed=553)
    contact = _click(0.04, 300, 3000, 0.004, 554)
    x = _mix([(_en(wood), 0.0, 1.0), (_en(boss), 0.0, 0.35), (_en(contact), 0.0, 0.3),
              (_en(rattle), 0.045, 0.12)], d)
    x = A.peak_eq(x, 450, 3.0, 1.0)
    x = A.peak_eq(x, 900, 3.0, 1.0)
    x = _room(x, 0.6, 0.15, 31)
    return _finish(x, "power_shield", 0.3, hp=70)


def _shield_steel() -> np.ndarray:
    """A steel shield takes a firm blow and rings out on D: a real tubular bell (a steel
    tube) gives the ring its voice, under the shield's own beating steel tones and the
    crack of the blow."""
    bell = _damp(_one(GM["tubular_bells"], "D5", 0.4, 100, 2.0, "fluid"), 0.45, 0.2)
    f0 = N("D4")
    ratios = [1.0, 1.59, 2.14, 3.0, 3.42, 4.2, 5.03, 6.1, 7.3]
    gains = [0.5, 0.45, 0.6, 0.8, 0.4, 0.4, 0.3, 0.2, 0.12]
    t60s = [1.2, 0.9, 0.85, 1.0, 0.6, 0.5, 0.42, 0.36, 0.3]
    plate = _modal(1.2, [(f0 * r, T, g) for r, T, g in zip(ratios, t60s, gains)], 0.00025, seed=601, rough=0.5,
                   split=0.0025)
    crack = _click(0.03, 1500, 6500, 0.0015, 602)
    body = A.lowpass(_noise(_n(0.08), 603), 900, 2) * _env(0.08, 0.015, 0.001)
    x = _mix([(_en(plate), 0.0, 1.0), (_en(bell), 0.0, 0.7), (_en(crack), 0.0, 0.25), (_en(body), 0.0, 0.35)],
             1.25)
    x = _damp(x, 0.55, 0.16, 1.17)
    x = _room(x, 0.7, 0.18, 32)
    return _finish(x, "power_shield", 0.3, hp=90)


def _leather(d: float, seed: int, rate: float = 170.0, f: float = 460.0) -> np.ndarray:
    """A leather strap creaking under a pull: stick-slip, a quick irregular train of tiny
    releases (faster as the pull grows, then easing), each ringing the strap's damped
    body."""
    rng = np.random.default_rng(seed)
    n = _n(d)
    exc = np.zeros(n)
    t = 0.0
    while t < d:
        u = t / d
        r = rate * (0.5 + math.sin(math.pi * u))
        t += rng.exponential(1.0 / r) * 0.7 + 0.3 / r
        i = _n(t)
        if i < n:
            exc[i] = rng.uniform(0.3, 1.0) * (0.35 + 0.65 * math.sin(math.pi * min(1.0, u)))
    y = sum(g * _reson(exc, f * k, T) for k, g, T in ((1.0, 1.0, 0.012), (1.83, 0.6, 0.008), (2.9, 0.3, 0.005),
                                                       (0.55, 0.5, 0.015)))
    return A.bandpass(y, 250, 4000, 1)


def _shield_raise() -> np.ndarray:
    """A shield lifted onto the arm: the leather straps creak, the buckle chinks, and
    the wooden shield settles against the arm with a soft knock."""
    d = 0.9
    creak = _leather(0.2, 651)
    buckle = _modal(0.3, [(2480, 0.09, 1.0), (3790, 0.06, 0.5), (5120, 0.04, 0.2)], 0.0003,
                    hits=((0.0, 1.0), (0.032, 0.45)), seed=652, split=0.004)
    knock = _modal(0.5, [(196, 0.09, 1.0), (294, 0.08, 0.9), (447, 0.06, 0.6), (650, 0.045, 0.4), (910, 0.03, 0.2)],
                   0.003, seed=653, rough=0.3)
    pat = A.lowpass(_noise(_n(0.05), 654), 1200, 2) * _env(0.05, 0.008, 0.001)
    x = _mix([(_en(buckle), 0.0, 0.2), (_en(creak), 0.004, 0.8), (_en(knock), 0.15, 1.0), (_en(pat), 0.15, 0.3)], d)
    x = _room(x, 0.5, 0.15, 33)
    return _finish(x, "power_shield", 0.25, hp=90)


def _shield_ward() -> np.ndarray:
    """A ward settles around you: a soft choir hums a low D chord, a bowed cello swells
    under it, and a celesta touches a high A."""
    hum = _bank([Note(GM["voice_oohs"], nm, 0.0, 0.6, vel=v) for nm, v in
                 (("A3", 92), ("D4", 90), ("F#4", 80), ("A4", 78))], 2.0, "fluid")
    hum = _damp(hum, 0.3, 0.2)
    cello = _bank([Note(GM["cello"], "D3", 0.0, 0.4, vel=96, swell=(110, 70))], 2.0, "fluid")
    harp = _one(GM["harp"], "D3", 0.6, 90, 2.0, "musescore")
    cel = _one(GM["celesta"], "A5", 0.3, 60, 1.6, "musescore")
    x = _mix([(_en(hum), 0.0, 1.0), (_en(cello), 0.0, 0.4), (_en(harp), 0.0, 0.35), (_en(cel), 0.05, 0.18)], 1.3)
    x = A.peak_eq(x, 160, -3.0, 0.8)
    x = _damp(x, 0.5, 0.15, 1.17)
    x = _room(x, 1.1, 0.28, 34)
    return _finish(x, "power_shield", 0.3, hp=80)


def _shield_steadfast() -> np.ndarray:
    """A harp and a lute strike one firm, low D chord together, and a bowed cello holds
    the D beneath them: steady as a raised shield."""
    harp = _bank([Note(GM["harp"], nm, 0.006 * k, 0.8, vel=100) for k, nm in
                  enumerate(("D3", "A3", "D4", "F#4", "A4", "D5"))], 2.0, "musescore")
    lute = _bank([Note(GM["nylon_guitar"], nm, 0.008 * k, 0.8, vel=96) for k, nm in
                  enumerate(("D3", "A3", "D4", "F#4", "A4"))], 2.0, "fluid")
    cello = _bank([Note(GM["cello"], "D3", 0.0, 0.5, vel=110, swell=(127, 80))], 2.0, "fluid")
    x = _mix([(_en(harp), 0.0, 0.85), (_en(lute), 0.0, 0.7), (_en(cello), 0.0, 0.5)], 1.3)
    x = A.peak_eq(x, 160, -4.0, 0.8)
    x = _damp(x, 0.55, 0.16, 1.17)
    x = _room(x, 0.8, 0.2, 35)
    return _finish(x, "power_shield", 0.3, hp=80)


# ============================================================================= blocked (immune)
def _blocked_fizzle() -> np.ndarray:
    """A spell fizzles out like a snuffed candle: a fiddle's note sags and fades, a breath
    puffs, and the wick sputters a few last weak crackles."""
    d = 0.95
    fid = _bank([Note(GM["fiddle"], "A4", 0.0, 0.42, vel=100, bend=(0.0, -5.0), swell=(127, 25))], 1.6, "fluid")
    fid = _damp(fid, 0.36, 0.06)
    pop = _modal(0.05, [(1850, 0.006, 1.0), (2900, 0.004, 0.6), (1100, 0.008, 0.5)], 0.0003, seed=850)
    tp = _t(0.18)
    puff = A.lowpass(_noise(_n(0.18), 851), 1400, 2) * (1 - np.exp(-tp / 0.004)) * np.exp(-tp / 0.05)
    sputter = _crackle(0.6, (45.0, 10.0), (1300.0, 3200.0), 852, ring=0.003, spread=0.5)
    sputter *= np.exp(-_t(0.6) / 0.22)
    x = _mix([(_en(pop), 0.0, 0.3), (_en(fid), 0.0, 1.0), (_en(puff), 0.0, 0.3), (_en(sputter), 0.05, 0.25)], d)
    x = _room(x, 0.5, 0.15, 41)
    return _finish(x, "power_blocked", 0.25, hp=110)


def _blocked_clank() -> np.ndarray:
    """A dull clank, as if the blow hit padded armour: a steel plate's modes smothered
    by the quilted padding behind it, and the cloth's soft thud."""
    d = 0.6
    f0 = N("D4")
    plate = _modal(d, [(f0 * r, T, g) for r, T, g in ((1.0, 0.16, 1.0), (1.71, 0.12, 0.75), (2.53, 0.09, 0.5),
                                                        (3.48, 0.07, 0.3), (4.62, 0.05, 0.18))],
                   0.0007, seed=801, rough=0.4, split=0.003)
    pad = A.lowpass(_noise(_n(0.08), 802), 800, 2) * _env(0.08, 0.014, 0.0015)
    pad = _reson(pad, 330, 0.05) * 0.6 + pad
    x = _mix([(_en(plate), 0.0, 1.0), (_en(pad), 0.0, 0.3), (_en(plate), 0.045, 0.1)], d)
    x = A.peak_eq(x, 750, 3.0, 0.9)
    x = A.lowpass(x, 3200, 2)
    x = _room(x, 0.4, 0.1, 42)
    return _finish(x, "power_blocked", 0.25, hp=90)


def _door(f: float, d: float, seed: int, soft: float = 1.0) -> np.ndarray:
    """A knuckle on a heavy oak door: the panel's low, quickly damped modes and the
    knuckle's hard little knock."""
    modes = [(f * 0.5, 0.1, 0.35), (f * 0.77, 0.09, 0.7), (f, 0.08, 1.0), (f * 1.46, 0.06, 0.75), (f * 2.1, 0.045, 0.5),
             (f * 3.05, 0.03, 0.25)]
    y = _modal(d, modes, 0.0014 * soft, seed=seed, rough=0.35)
    k = _click(0.02, 900, 3500, 0.0012, seed + 1)
    return A.peak_eq(_en(y) + 0.15 * _len(_en(k), d), 700, 4.0, 0.9)


def _blocked_knock() -> np.ndarray:
    """Two dull knocks on a heavy wooden door, the second lower: nothing gets through."""
    x = _mix([(_door(N("A4"), 0.4, 901), 0.0, 1.0), (_door(N("F4"), 0.4, 902, 1.2), 0.17, 0.9)], 0.75)
    x = _room(x, 0.5, 0.12, 43)
    return _finish(x, "power_blocked", 0.2, hp=90)


def _blocked_stone() -> np.ndarray:
    """The blow lands on solid stone: a deep, dead thud, the stone's hard short knock, and a
    little grit trickling down the wall."""
    d = 0.85
    thud = A.lowpass(_noise(_n(0.2), 951), 400, 2) * _env(0.2, 0.03, 0.002)
    thud = _reson(thud, 110, 0.08) * 0.5 + _reson(thud, 260, 0.05) * 0.5 + thud
    knock = _modal(d, [(N("D4"), 0.07, 1.0), (N("A4") * 1.03, 0.05, 0.7), (N("D4") * 2.63, 0.035, 0.5),
                       (N("D4") * 4.1, 0.02, 0.25)], 0.0014, seed=952, rough=0.6)
    grit = _crackle(0.4, (600.0, 60.0), (600.0, 2400.0), 953, ring=0.0018, spread=0.3)
    grit *= np.exp(-_t(0.4) / 0.12) * np.clip(_t(0.4) / 0.03, 0, 1)
    x = _mix([(_en(thud), 0.0, 0.22), (_en(knock), 0.0, 1.0), (_en(_click(0.03, 500, 2500, 0.006, 954)), 0.0, 0.3),
              (_en(grit), 0.05, 0.13)], d)
    x = A.peak_eq(x, 700, 4.0, 0.9)
    x = _room(x, 0.45, 0.12, 44)
    return _finish(x, "power_blocked", 0.25, hp=70, shave=8.0)


def _blocked_string() -> np.ndarray:
    """A low lute string is plucked and stopped dead at once by the palm, with a knock on
    the lute's wooden body: a flat, dull 'thup'."""
    s = _one(GM["nylon_guitar"], "D3", 0.3, 110, 1.2, "fluid")
    s = _damp(s, 0.05, 0.03)
    s2 = _one(GM["nylon_guitar"], "A3", 0.3, 80, 1.2, "musescore")
    s2 = _damp(s2, 0.04, 0.025)
    body = _modal(0.3, [(210, 0.06, 1.0), (395, 0.05, 0.7), (620, 0.03, 0.4)], 0.002, seed=971)
    x = _mix([(_en(s), 0.0, 1.0), (_en(s2), 0.0, 0.35), (_en(body), 0.0, 0.35)], 0.6)
    x = A.peak_eq(x, 400, 3.0, 1.0)
    x = _room(x, 0.45, 0.12, 45)
    return _finish(x, "power_blocked", 0.2, hp=90)


# ============================================================================= the list
CANDIDATES = [
    Candidate("power_heal", "potion_bubbles", "Potion bubbles",
              "A cork comes out of a little glass bottle, the potion bubbles up and fizzes, and the glass "
              "clinks softly with a celesta note.", _heal_bubbles, ["realistic", "liquid"]),
    Candidate("power_heal", "harp_rise", "Harp rise",
              "A real harp sweeps gently up a warm D major chord and lets it ring a moment.", _heal_harp,
              ["courtly", "harp"]),
    Candidate("power_heal", "warm_glow", "Warm glow",
              "A soft harp note blooms into a quiet, warm swell of bowed strings.", _heal_glow, ["soft", "strings"]),
    Candidate("power_heal", "holy_light", "Holy light",
              "A choir sings out a bright chord as a celesta climbs above it.", _heal_holy, ["grand", "choir"]),
    Candidate("power_heal", "healer_tune", "Healer's tune",
              "A wooden recorder plays a quick rising tune over a strummed lute.", _heal_tune, ["tavern", "recorder"]),
    Candidate("power_double", "twin_strike", "Twin strike",
              "Two quick sword blows, the second one harder, ringing and scraping steel on steel.", _double_twin,
              ["realistic", "metal"]),
    Candidate("power_double", "power_surge", "Power surge",
              "A quick drum roll swells and bursts into two bright orchestra strikes (brass, kettledrum, "
              "glockenspiel), the second higher with a cymbal.", _double_surge, ["grand", "orchestra"]),
    Candidate("power_double", "war_drums", "Double boom",
              "Two big war kettledrums: boom, then a bigger, deeper BOOM.", _double_drums, ["drums", "deep"]),
    Candidate("power_double", "war_horn", "Rallying horns",
              "Two French horns call out together: a short note, then a longer, strong one.", _double_horn,
              ["courtly", "brass"]),
    Candidate("power_double", "table_pound", "Table pound",
              "A fist pounds the tavern table twice and the pewter tankards jump and clatter.", _double_table,
              ["tavern", "wooden"]),
    Candidate("power_shield", "shield_bash", "Shield bash",
              "A blow thuds into a wooden shield: the planks boom, the iron boss clanks and the rim rattles.",
              _shield_bash, ["realistic", "wooden"]),
    Candidate("power_shield", "steel_ring", "Steel ring",
              "A steel shield takes a firm blow and rings out like a struck bell.", _shield_steel, ["metal", "ringing"]),
    Candidate("power_shield", "raise_shield", "Raise shield",
              "A quiet one: leather straps creak, a buckle chinks and the shield settles on the arm with a soft "
              "knock.", _shield_raise, ["soft", "leather"]),
    Candidate("power_shield", "ward_hum", "Ward hum",
              "A soft choir hums a low chord over a bowed cello as a ward settles around you.", _shield_ward,
              ["mysterious", "choir"]),
    Candidate("power_shield", "steadfast", "Steadfast",
              "A harp and a lute strike one firm low chord while a cello holds the note beneath.", _shield_steadfast,
              ["courtly", "strings"]),
    Candidate("power_blocked", "fizzle", "Fizzle",
              "A spell fizzles like a snuffed candle: a fiddle note sags away, a breath puffs and the wick "
              "sputters out.", _blocked_fizzle, ["magical", "fiddle"]),
    Candidate("power_blocked", "muffled_clank", "Muffled clank",
              "A dull clank, as if the blow hit padded armour.", _blocked_clank, ["realistic", "dull"]),
    Candidate("power_blocked", "dull_knock", "Dull knock",
              "Two dull knocks on a heavy wooden door, the second lower: nothing gets through.", _blocked_knock,
              ["wooden", "soft"]),
    Candidate("power_blocked", "stone_wall", "Stone wall",
              "A dead, heavy thud against solid stone, with a little grit falling.", _blocked_stone,
              ["realistic", "deep"]),
    Candidate("power_blocked", "stopped_string", "Stopped string",
              "A low lute string is plucked and stopped dead at once by the palm: a flat 'thup'.", _blocked_string,
              ["courtly", "string"]),
]


# ============================================================================= the editor's pass
# Two finishing touches over the whole family, applied after each candidate renders:
#  - a phone's small speaker plays almost nothing below 300 Hz: a sound that would lose
#    more than PHONE_MAX_LOSS dB of its loudness there gets a gentle low shelf (at most
#    -8 dB below about 250 Hz), so after mastering its body is that much more present;
#  - the app starts the hit once 60% of the power's file has played (0.24 s after it at
#    the soonest), so a long power holds up the whole turn: the ringers are damped from
#    ``start`` (a hand on the strings, the room settling) and over by ``end``.
PHONE_MAX_LOSS = 3.0
TAILS = {
    ("power_double", "power_surge"): (0.36, 0.68), ("power_double", "table_pound"): (0.30, 0.62),
    ("power_double", "twin_strike"): (0.30, 0.70), ("power_double", "war_drums"): (0.40, 0.70),
    ("power_double", "war_horn"): (0.45, 0.75),
    ("power_shield", "steadfast"): (0.40, 0.72), ("power_shield", "steel_ring"): (0.32, 0.65),
    ("power_shield", "ward_hum"): (0.40, 0.72),
    ("power_blocked", "fizzle"): (0.50, 0.72),
    ("power_heal", "harp_rise"): (0.60, 1.05), ("power_heal", "healer_tune"): (0.65, 1.10),
    ("power_heal", "holy_light"): (0.60, 1.05), ("power_heal", "potion_bubbles"): (0.85, 1.15),
    ("power_heal", "warm_glow"): (0.55, 1.00),
}


def _low_shelf(x: np.ndarray, f0: float, gain_db: float, q: float = 0.707) -> np.ndarray:
    """A low shelf (RBJ biquad): ``gain_db`` below ``f0``, half of it at ``f0``."""
    a_ = 10 ** (gain_db / 40.0)
    w0 = TAU * f0 / SR
    al = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    s2 = 2 * math.sqrt(a_) * al
    b = [a_ * ((a_ + 1) - (a_ - 1) * c + s2), 2 * a_ * ((a_ - 1) - (a_ + 1) * c), a_ * ((a_ + 1) - (a_ - 1) * c - s2)]
    a = [(a_ + 1) + (a_ - 1) * c + s2, -2 * ((a_ - 1) + (a_ + 1) * c), (a_ + 1) + (a_ - 1) * c - s2]
    return signal.lfilter(b, a, x)


def _phone_loss(x: np.ndarray) -> float:
    return A._rms_db(x) - A._rms_db(A.highpass(x, 300, 4))


def _phone(x: np.ndarray) -> np.ndarray:
    if _phone_loss(x) <= PHONE_MAX_LOSS:
        return x
    for g in range(1, 9):
        y = _low_shelf(x, 250.0, -float(g))
        if _phone_loss(y) <= PHONE_MAX_LOSS:
            break
    return y


def _hasten(x: np.ndarray, start: float, end: float, drop_db: float = 40.0) -> np.ndarray:
    """Damp what still rings after ``start``: an extra fall of ``drop_db`` by ``end``,
    where the sound stops (the last few milliseconds faded)."""
    i0, i1 = _n(start), min(len(x), _n(end))
    if len(x) <= i0:
        return x
    y = x[:i1].copy()
    y[i0:] *= 10 ** (-drop_db / 20.0 * np.arange(i1 - i0) / max(1, i1 - i0))
    k = min(len(y), _n(0.006))
    y[-k:] *= np.linspace(1.0, 0.0, k)
    return y


def _edited(c: Candidate) -> Candidate:
    tail = TAILS.get((c.event, c.id))
    render = c.render

    def run() -> np.ndarray:
        x = _phone(render())
        return _hasten(x, *tail) if tail else x
    return dataclasses.replace(c, render=run)


CANDIDATES = [_edited(c) for c in CANDIDATES]
