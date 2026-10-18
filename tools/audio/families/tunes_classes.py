"""Info pop-up clips of the classes group (docs/INFO_POPUPS.md, "Melody plan", LEITMOTIFS):
the stamped IMMUNITY card, the nine class cards and the plain Damage card.

One instrument per class, so a Goran attack (Cleric, Bard, Warrior, then Damage or
Defeated) sounds like the tavern band taking turns:

  Mage      celesta and harp harmonics, D lydian: D E G# A, a curious question on A
  Druid     wooden pan flute, D dorian, bird trills over a leaf rustle (shaker); the
            game's shuffle, then a quick deal; hangs on A
  Cleric    harp: a rising D-major arpeggio ringing on high D, a hand bell on the top
            note; the game's shuffle first
  Bard      lute: a strummed run up the scale, a rolled chord, a skipping turn; the
            game's draw first
  Chanter   humming voices over a low drone: a plainchant call that rises and waits on A
  Reaver    cello and woodblock: the digging figure D A F D, stopping on an open low A
  Warrior   fiddle and tabor: a stamping double-stop figure, then the same an octave up
            (the doubling), each landing on a hard tabor hit
  Paladin   French horns: a calm D-A fifth with a struck shield ringing under it
  Guardian  low bowed strings and timpani: a D-major wall rising, held firm (half time)
  Damage    bodhran and lute: a strummed D-minor stab in a dotted strike, D D A
  IMMUNITY  the IMMUNITY jig, the Whistle jig's dark twin: its rhythm on bassoon and
            fiddle in D minor runs into a wooden stamp thump and droops away on a
            comic falling slide

Mage, Druid, Chanter and Reaver stand just before their decision box: they end open on
A (the owner's ruling: no result cards follow them). Everything else ends on D. Every
clip is built by ``_info_common.clip`` (the shared pickup, cadence, tail, room and master).

Private helpers (struck things no bank records, modelled from their physics as the
combat and powers families do): ``_shield`` (a steel-bossed shield struck once: a few
inharmonic, slowly beating modes over the wood's knock) and ``_stamp`` (the IMMUNITY
stamp: a padded wooden thump, a concert bass drum and a frame drum under a dull wooden
knock).
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

import numpy as np
from scipy import signal

from _info_common import (BAR, DQ, EIGHTH, MOTIF, SIXTEENTH, SR, A, INote, at, beats, card_sound, choke, clip, fit,
                          hit, info, n, perc, phrase, render, roll, trill)

# ============================================================================= helpers
Part = Tuple[np.ndarray, float, float]          # (audio, seconds from 0, linear gain)


def _tail(x: np.ndarray, floor_db: float = -70.0) -> np.ndarray:
    """Cut what stays below ``floor_db`` (re the peak) at the end; the start is kept, so
    timing holds. A layer is then measured by its sound, not by silence after it (clip's
    ``level`` takes the 95th percentile of 50 ms blocks)."""
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak <= 0:
        return x
    idx = np.nonzero(np.abs(x) > peak * 10 ** (floor_db / 20.0))[0]
    end = min(len(x), int(idx[-1]) + A.n_of(0.02))
    y = x[:end].copy()
    k = min(len(y), A.n_of(0.02))
    y[-k:] *= np.linspace(1.0, 0.0, k)
    return y


def _top(x: np.ndarray) -> float:
    """The loudest 50 ms block (dB): how loud a single stroke hits."""
    blk = A.n_of(0.05)
    k = max(1, len(x) // blk)
    y = fit(A.highpass(x, 100, 1), k * blk / SR)
    return 10 * math.log10(float(np.max(np.mean(y.reshape(k, blk) ** 2, axis=1))) + 1e-20)


def _at_top(x: np.ndarray, db: float) -> np.ndarray:
    return x * 10 ** ((db - _top(x)) / 20.0)


def _mixdown(parts: Sequence[Part], seconds: float = 2.6) -> np.ndarray:
    """Mix ``(audio, t, gain)`` parts into one buffer (t from 0), its silent end cut."""
    x = np.zeros(A.n_of(seconds))
    for y, t, g in parts:
        x = A.mix_at(x, y, t, g)
    return _tail(x)


def _strokes(name_: str, hits: Sequence[Tuple[float, int]], seconds: float = 2.6) -> np.ndarray:
    """A tavern percussion part: ``perc(name_)`` struck at (t, velocity); the strokes keep
    their relative levels (the velocity's square law, as a player's touch)."""
    parts = []
    for t, v in hits:
        parts.append((perc(name_, 110), t, (v / 110.0) ** 2))
    return _mixdown(parts, seconds)


def _reson(x: np.ndarray, f: float, t60: float) -> np.ndarray:
    """A two-pole resonator ringing at ``f`` for ``t60`` seconds."""
    w = 2 * math.pi * f / SR
    r = 0.001 ** (1.0 / (t60 * SR))
    return signal.lfilter([math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], x)


def _shield(f0: float = 293.66, seconds: float = 1.6, seed: int = 31) -> np.ndarray:
    """A round shield with a steel boss, struck once with a sword's pommel: the boss rings
    on a few inharmonic modes (each a slightly detuned pair, so it beats slowly), the
    first two near D and A; the wooden board under it gives a short, dull knock."""
    rng = np.random.default_rng(seed)
    burst = A.lowpass(rng.standard_normal(A.n_of(0.0025)), 4200, 2) * np.hanning(A.n_of(0.0025))
    ex = fit(burst, seconds)
    modes = [(1.0, 1.0, 1.25), (1.5 * 1.003, 0.55, 1.0), (2.33, 0.42, 0.7), (2.97, 0.3, 0.55), (3.71, 0.22, 0.42),
             (4.62, 0.13, 0.32), (5.58, 0.08, 0.25)]
    ring = np.zeros(A.n_of(seconds))
    for r, g, t60 in modes:
        f = f0 * r
        if f > 6500:
            break
        ring += g * _reson(ex, f * 0.9985, t60) + 0.8 * g * _reson(ex, f * 1.0015, t60 * 0.9)
    board = A.lowpass(rng.standard_normal(A.n_of(0.06)), 700, 2) * np.exp(-np.arange(A.n_of(0.06)) / (0.012 * SR))
    board = _reson(fit(board, 0.3), 180, 0.08) * 0.4 + _reson(fit(board, 0.3), 410, 0.05) * 0.3
    x = ring / (np.max(np.abs(ring)) or 1.0)
    x = A.mix_at(x, 0.5 * board / (np.max(np.abs(board)) or 1.0), 0.0)
    return _tail(A.lowpass(x, 5000, 2))


def _stamp() -> np.ndarray:
    """The IMMUNITY stamp landing on the card: a padded wooden thump (a concert bass drum
    and a frame drum, damped at once) under the dull knock of the stamp's wooden block."""
    bd = choke(hit("bass_drum", 118, kit="orchestra"), 0.05, 0.22)
    fd = perc("frame_drum", 124)
    wb = choke(hit("low_woodblock", 96), 0.02, 0.08)
    body = A.lowpass(np.random.default_rng(77).standard_normal(A.n_of(0.05)), 900, 2)
    body *= np.exp(-np.arange(len(body)) / (0.01 * SR))
    body = _reson(fit(body, 0.3), 240, 0.06) + 0.6 * _reson(fit(body, 0.3), 520, 0.04)
    ref = _top(bd)
    x = _mixdown([(bd, 0.0, 1.0), (_at_top(fd, ref - 2.0), 0.0, 1.0), (_at_top(wb, ref - 9.0), 0.004, 1.0),
                  (_at_top(body, ref - 5.0), 0.0, 1.0)], 1.2)
    return _tail(A.peak_eq(x, 420, 4.0, 1.0))     # the thump's body where a phone plays it


def _harmonics(notes: Sequence[Tuple[str, float, int]], seconds: float = 2.6) -> np.ndarray:
    """Harp harmonics: plucked softly and stopped at the string's middle they sound an
    octave up, pure and bell-like (the bank's harp, its top taken away, the ring shorter)."""
    y = render([n("harp", p, t, 0.4, vel=v) for p, t, v in notes], seconds)
    return _tail(A.lowpass(y, 2400, 4))


def _flicks(times: Sequence[float]) -> np.ndarray:
    """A quick deal: the game's card flick (the owner's pick), softened, once per card."""
    f = A.lowpass(card_sound("flick"), 4500, 2)
    return _mixdown([(f, t, 1.0 - 0.15 * i) for i, t in enumerate(times)], 1.0)


def _bell(pitch: str = "D6", vel: int = 44) -> np.ndarray:
    """A hand bell touched softly (the bank's tubular bell, its sharp top taken away)."""
    return _tail(A.lowpass(render([n("hand_bell", pitch, 0.0, 0.6, vel=vel)], 2.0), 3200, 2))


def _timp_roll(pitch: str, start: float, dur: float, v0: int, v1: int, rate: float = 0.06) -> List[INote]:
    """A timpani roll swelling from ``v0`` to ``v1`` (single strokes ``rate`` s apart)."""
    k = max(2, int(round(dur / rate)))
    return [n("timpani", pitch, start + i * rate, rate * 1.6, vel=int(round(v0 + (v1 - v0) * i / (k - 1))))
            for i in range(k)]


def _droop(inst: str, pitch: str, hold: float, glide: float, after: float = 0.5, fall: float = 7.0,
           vel: int = 104, ring: float = 0.5) -> np.ndarray:
    """A comic droop: a held note that sags ``fall`` semitones over ``glide`` seconds
    (slowly, then faster, then settling) and stays at the bottom, dying away over
    ``ring`` s. The recording itself is slowed as it plays (a varispeed), so the note
    lands and holds its lower pitch, as a bassoonist's or fiddler's sagging slide does
    (a pitch bend would leave only the release at the bottom)."""
    total = hold + glide + after
    src = render([n(inst, pitch, 0.0, total, vel=vel, swell=(116, 96))], total + 0.6)
    t = np.arange(A.n_of(total)) / SR
    u = np.clip((t - hold) / glide, 0.0, 1.0)
    semis = -fall * (1 - np.cos(math.pi * u)) / 2
    pos = np.concatenate([[0.0], np.cumsum(2 ** (semis[:-1] / 12.0))])
    y = np.interp(pos, np.arange(len(src)), src, right=0.0)
    env = np.where(t < hold + glide, 1.0, np.exp(-6.9078 * np.clip(t - hold - glide, 0, None) / ring))
    y = y * env
    k = A.n_of(0.02)
    y[-k:] *= np.linspace(1.0, 0.0, k)
    return y


# ============================================================================= IMMUNITY
# The Whistle jig (combat.py) is A5 B5 A5 F#5 D5 F#5 A5 B5 | D6 in eighths; its dark twin
# is the same rhythm in D minor (B flat, F natural), low on a bassoon with a fiddle.
def _soft_tabor(hits: Sequence[Tuple[float, int]]) -> np.ndarray:
    """The jig's tabor, its snare wires' sizzle taken down."""
    return A.lowpass(_strokes("tabor", hits), 4500, 2)


def _immunity_jig() -> np.ndarray:
    """Bassoon leads, the fiddle an octave up; the stamp lands where the jig's high D
    would be, and after a stunned eighth the bassoon droops a fifth down to D."""
    motif = phrase("bassoon", "A3 Bb3 A3 F3 D3 F3 A3 Bb3", vel=102, legato=0.85, seed=11)
    motif += phrase("fiddle", "A4 Bb4 A4 A4/F4 D4 F4 A4 Bb4", vel=78, legato=0.8, seed=12)
    sag = _droop("bassoon", "A3", 0.1, 0.46, after=0.62, vel=108)
    tabor = _soft_tabor([(0.0, 70), (DQ, 56), (BAR, 62)])
    return clip(motif, end="D", mood="minor", instrument=None, pickup="harp", cadence_at=at(1, 3) + 0.56,
                bed=None, tail=False, layers=[(tabor, 0.0, -16.0), (_stamp(), at(1, 2), 2.0), (sag, at(1, 3))],
                length=2.28)


def _immunity_stamp() -> np.ndarray:
    """The fiddle leads with a bassoon oom-pah; the stamp lands a bar in, and fiddle and
    bassoon sag down a fifth to D together."""
    motif = phrase("fiddle", "A4 Bb4 A4 A4/F4 D4 F4", vel=92, legato=0.8, seed=21)
    motif += phrase("bassoon", "D3:2 r:1 A2:2 r:1", vel=92, legato=0.55, seed=22)
    drop = at(1, 1) + 0.03
    sag = _droop("fiddle", "A4", 0.08, 0.5, after=0.66, vel=94)
    low = _droop("bassoon", "A2", 0.08, 0.5, after=0.66, vel=100)
    k = min(len(sag), len(low))
    tabor = _soft_tabor([(0.0, 72), (DQ, 58)])
    return clip(motif, end="D", mood="minor", instrument=None, pickup="flick", cadence_at=drop + 0.58,
                bed=None, tail=False, layers=[(tabor, 0.0, -16.0), (_stamp(), BAR, 2.0), (sag[:k] + low[:k], drop)],
                length=2.26)


# ============================================================================= Mage (before its box: A)
def _mage_peek() -> np.ndarray:
    """Celesta: D E G# A, then a tiptoe round the raised fourth back up to A; harp
    harmonics chime on the beats."""
    motif = phrase("celesta", "D5 E5 G#5 A5:3 B5 A5 G#5 E5:2 G#5", vel=84, seed=31)
    harm = _harmonics([("D5", 0.0, 70), ("A5", DQ, 62), ("E5", BAR, 64), ("G#5", BAR + DQ, 58)])
    return clip(motif, end="A", mood="magic", instrument="celesta", layers=[(harm, 0.0, -7.0)])


def _mage_slow() -> np.ndarray:
    """The same question at half time: D, E, the raised G#, then A held with a trembling
    shimmer, a last B leaning back onto A."""
    motif = phrase("celesta", "D5 E5 G#5 A5:2 B5", vel=82, slow=True, seed=32)
    motif += trill("celesta", "A5", "G#5", at(1, 1), 0.3, vel=46, rate=0.056)
    harm = _harmonics([("D5", 0.0, 70), ("G#5", 0.44, 56), ("A5", 0.66, 64), ("E6", 1.1, 46)])
    return clip(motif, end="A", mood="magic", instrument="celesta", slow=True, held_vel=80,
                layers=[(harm, 0.0, -6.0)])


# ============================================================================= Druid (before its box: A)
def _rustle(seconds: float = 1.6, seed: int = 41) -> np.ndarray:
    """Leaves stirring: a shaker brushed on every eighth, unevenly."""
    rng = np.random.default_rng(seed)
    hits = [(i * EIGHTH + float(rng.uniform(-0.01, 0.01)) + 0.01, int(rng.integers(46, 70)))
            for i in range(int(seconds / EIGHTH))]
    return _strokes("shaker", hits, seconds + 0.5)


def _druid_call() -> np.ndarray:
    """The game's shuffle, three cards dealt, then the pan flute's call up the dorian
    scale with a bird's trill on the high A; it hangs there."""
    motif = phrase("pan_flute", "A4 D5:2 A4 D5 F5", vel=88, seed=41)
    motif += phrase("pan_flute", "G5", at=at(1, 0), vel=90, seed=42)
    motif += trill("pan_flute", "A5", "B5", at(1, 1), beats(3) - 0.02, vel=84, rate=0.045)
    motif += phrase("pan_flute", "G5 F5", at=at(1, 4), vel=86, seed=43)
    return clip(motif, end="A", mood="bane", instrument="pan_flute", pickup="shuffle", held_vel=88,
                layers=[(_flicks([0.0, 0.07, 0.14]), -0.02, -12.0), (_rustle(), 0.0, -22.0)])


def _key_anchor(notes: Sequence[INote], until: float) -> np.ndarray:
    """A soft harp bass that names the key (D) under a call that ends open on A, damped
    just before the cadence so the open A-E fifth stands alone (without it a call built
    on A, C and E is heard in A minor, and its A sounds like home, not a question)."""
    return _tail(choke(render(notes, 2.6), until, 0.12))


def _druid_birds() -> np.ndarray:
    """The shuffle and the deal, then a low earthy call (a trill on D falling to A) over a
    soft harp D, birds answering high up, and the call left hanging on the low A."""
    motif = trill("pan_flute", "D5", "E5", 0.0, beats(2) - 0.02, vel=84, rate=0.05)
    motif += phrase("pan_flute", "C5 A4:3", at=beats(2), vel=86, seed=44)
    motif += phrase("pan_flute", "B5/A5 F5", at=at(1, 0), vel=78, seed=45)
    motif += trill("pan_flute", "G5", "A5", at(1, 2), beats(2) - 0.02, vel=74, rate=0.045)
    motif += phrase("pan_flute", "E5 C5", at=at(1, 4), vel=80, seed=46)
    anchor = _key_anchor([n("harp", "D3", 0.0, 0.6, vel=64), n("harp", "A3", 0.014, 0.6, vel=54),
                          n("harp", "D3", BAR, 0.6, vel=56)], MOTIF - 0.03)
    return clip(motif, end="A4", mood="bane", instrument="pan_flute", pickup="shuffle", held_vel=86,
                layers=[(_flicks([0.0, 0.08]), -0.02, -12.0), (_rustle(seed=47), 0.0, -21.0),
                        (anchor, 0.0, -10.0)])


# ============================================================================= Cleric (D)
def _cleric_rise() -> np.ndarray:
    """The game's shuffle, then the harp climbs D F# A D, F# A, and rings out on high D
    as a hand bell touches it."""
    motif = phrase("harp", "D4 F#4 A4 D5:3 F#5 A5:2", vel=80, seed=51, legato=1.6)
    motif.append(n("harp", "D3", 0.0, 1.2, vel=64))
    cad = at(1, 3)
    return clip(motif, end="D", mood="party", instrument="harp", pickup="shuffle", cadence_at=cad, hold=0.6,
                held_vel=90, layers=[(_bell(), cad + 0.012, -10.0)])


def _cleric_waves() -> np.ndarray:
    """The game's shuffle, then two rising waves on the harp (D F# A D, then from F#
    up to A) over a falling bass, lifting to a ringing high D with a hand bell."""
    motif = phrase("harp", "D4 F#4 A4 D5:3", vel=78, seed=52, legato=1.6)
    motif += phrase("harp", "F#4 A4 D5 F#5:2 A5", at=BAR, vel=80, seed=53, legato=1.6)
    motif += [n("harp", "D3", 0.0, 0.7, vel=66), n("harp", "A2", BAR, 0.7, vel=62)]
    return clip(motif, end="D", mood="party", instrument="harp", pickup="shuffle", held_vel=90,
                layers=[(_bell(), MOTIF + 0.012, -10.0)])


# ============================================================================= Bard (D)
def _bard_run() -> np.ndarray:
    """The game's draw, then the lute runs up the scale into a strummed D chord and
    skips round a turn to D."""
    motif = phrase("lute", "D4 E4 F#4 G4 A4 B4", vel=84, seed=61, legato=1.2,
                   slow=False, grace=0.02)
    for x in motif:                                  # a run of sixteenths
        x.start = x.start / 2
        x.dur = SIXTEENTH * 1.2
    motif += roll("lute", ["D3", "A3", "D4", "F#4", "A4"], DQ, 0.6, vel=92, spread=0.016)
    motif += phrase("lute", "F#5:2 E5 D5 E5 C#5", at=BAR, vel=86, seed=62)
    return clip(motif, end="D", mood="party", instrument="lute", pickup="draw", bed="lute", bed_db=-9.0)


def _bard_flourish() -> np.ndarray:
    """The game's draw, a strummed D chord and a skip, then a quick run up to a
    high F# and down to D on a last strum."""
    motif = roll("lute", ["D3", "A3", "D4", "F#4", "A4"], 0.0, 0.33, vel=94, spread=0.016)
    motif += phrase("lute", "A4:2 F#4", at=DQ, vel=84, seed=63)
    run = phrase("lute", "G4 A4 B4 C#5 D5 E5", at=0.0, vel=82, seed=64)
    for x in run:
        x.start = BAR + x.start / 2
        x.dur = SIXTEENTH * 1.2
    motif += run
    motif += phrase("lute", "F#5:2 E5", at=at(1, 3), vel=88, seed=65)
    motif += roll("lute", ["D3", "A3", "D4", "F#4"], MOTIF, 0.5, vel=80, spread=0.018)
    return clip(motif, end="D", mood="party", instrument="lute", pickup="draw", bed=None)


# ============================================================================= Chanter (before its box: A)
def _chanter_call() -> np.ndarray:
    """Humming voices over a low hummed drone on D and A: the call D E F#, E F# G, rising
    to wait on A as the drone opens to A and E."""
    motif = phrase("humming", "D4:2 E4 F#4:3 E4:2 F#4 G4:3", vel=86, legato=1.02, seed=71)
    motif += [n("humming", "D3", 0.0, MOTIF, vel=62, swell=(70, 100)),
              n("humming", "A3", 0.0, MOTIF, vel=54, swell=(70, 96)),
              n("humming", "A2", MOTIF, 0.5, vel=60, swell=(100, 40)),
              n("humming", "E3", MOTIF, 0.5, vel=52, swell=(100, 40))]
    return clip(motif, end="A", mood="party", instrument="humming", hold=0.5, bed="harp", bed_db=-15.0)


def _chanter_organum() -> np.ndarray:
    """Plainchant in organum, at half time: two humming voices a fourth apart over a
    hummed D, rising together to rest open on A and E."""
    top = phrase("humming", "D4 E4 F#4 E4:2 G4", vel=84, slow=True, legato=1.02, seed=72)
    low = phrase("humming", "A3 B3 C#4 B3:2 D4", vel=70, slow=True, legato=1.02, seed=73)
    motif = top + low + [n("humming", "D3", 0.0, MOTIF, vel=60, swell=(60, 96)),
                         n("humming", "E4", MOTIF, 0.6, vel=70, swell=(110, 40))]
    return clip(motif, end="A", mood="party", instrument="humming", slow=True, hold=0.6, bed="harp", bed_db=-15.0)


# ============================================================================= Reaver (before its box: A)
def _reaver_dig() -> np.ndarray:
    """Cello: the digging figure D A F D, twice, each stroke struck by a woodblock pick,
    then up a fourth to stop on an open low A."""
    motif = phrase("cello", "D3 A2 F2 D2:3 D3 A2 F2 D2:2 E2", vel=100, legato=0.72, seed=81)
    picks = _strokes("woodblock", [(0.0, 96), (EIGHTH, 70), (2 * EIGHTH, 78), (DQ, 104),
                                   (BAR, 96), (BAR + EIGHTH, 70), (BAR + 2 * EIGHTH, 78), (BAR + DQ, 104)])
    return clip(motif, end="A", mood="enemy", instrument="cello", held_vel=96, layers=[(picks, 0.0, -6.0)])


def _reaver_grave() -> np.ndarray:
    """A gravedigger's cello: two short strokes and a heave (D D A, F down to D), twice,
    the woodblock on each stroke and a muffled thud as the spade bites, then open A."""
    motif = phrase("cello", "D3 D3 A2 F2:2 D2 D3 D3 A2 F2:2 E2", vel=98, legato=0.6, seed=82)
    picks = _strokes("woodblock", [(0.0, 92), (EIGHTH, 80), (BAR, 92), (BAR + EIGHTH, 80)])
    thuds = _strokes("frame_drum", [(DQ, 96), (BAR + DQ, 100)])
    return clip(motif, end="A", mood="enemy", instrument="cello", held_vel=94,
                layers=[(picks, 0.0, -6.0), (thuds, 0.0, -8.0)])


# ============================================================================= Warrior (D)
def _warrior_stamp() -> np.ndarray:
    """Fiddle double stops, stamp - and - STAMP, each landing on a hard tabor hit, then
    the same an octave higher (the doubling), and a last stamp on D."""
    motif = phrase("violin", "D4+A4:2 A3+E4 D4+A4:3", vel=100, legato=0.8, seed=91)
    motif += phrase("violin", "D5+A5:2 A4+E5 D5+A5:3", at=BAR, vel=98, legato=0.8, seed=92)
    motif += [n("violin", "D5", MOTIF, 0.46, vel=100, swell=(118, 50)),
              n("violin", "A4", MOTIF, 0.46, vel=88, swell=(118, 50))]
    tabor = _soft_tabor([(0.0, 84), (2 * EIGHTH, 60), (DQ, 120), (BAR, 88), (BAR + 2 * EIGHTH, 62),
                         (BAR + DQ, 124), (MOTIF, 112)])
    return clip(motif, end="D", mood="party", instrument=None, layers=[(tabor, 0.0, -4.0)])


def _warrior_reel() -> np.ndarray:
    """A driving reel on the fiddle: A D F# and a double-stop stamp on the tabor, then
    the whole figure an octave higher, and a last stamp on D."""
    motif = phrase("violin", "A3 D4 F#4 D4+A4:3", vel=96, legato=0.8, seed=93)
    motif += phrase("violin", "A4 D5 F#5 D5+A5:3", at=BAR, vel=94, legato=0.8, seed=94)
    motif += [n("violin", "D4", MOTIF, 0.46, vel=96, swell=(118, 50)),
              n("violin", "D5", MOTIF, 0.46, vel=92, swell=(118, 50))]
    ghosts = [(i * EIGHTH, 46) for i in range(12) if i not in (0, 3, 6, 9)]
    tabor = _soft_tabor(ghosts + [(0.0, 82), (DQ, 120), (BAR, 86), (BAR + DQ, 124), (MOTIF, 112)])
    return clip(motif, end="D", mood="party", instrument=None, layers=[(tabor, 0.0, -4.0)])


# ============================================================================= Paladin (D)
def _paladin_fifth() -> np.ndarray:
    """Two French horns hold a calm D-A fifth over a struck shield's ring, then the upper
    horn climbs A B C# to D, held over the low D."""
    motif = [n("horn", "D3", 0.0, MOTIF + 0.5, vel=84, swell=(80, 104)),
             n("horn", "A3", 0.0, BAR - 0.02, vel=90, swell=(84, 108))]
    motif += phrase("horn", "B3:3 C#4:3", at=BAR, vel=90, legato=0.98, seed=101)
    return clip(motif, end="D", mood="party", instrument="horn", held_vel=94, hold=0.5,
                layers=[(_shield(), 0.0, -5.0)])


def _paladin_call() -> np.ndarray:
    """A noble horn call over a held horn D (D up to A, then down G F# E) that lands on
    D as the shield is struck and rings under it."""
    motif = phrase("horn", "D4:3 A4:3 G4:2 F#4 E4:3", vel=88, legato=0.98, seed=102)
    motif += [n("horn", "D3", 0.0, BAR - 0.02, vel=80, swell=(84, 100)),
              n("horn", "A3", BAR, BAR - 0.02, vel=78, swell=(84, 100)),
              n("horn", "D3", MOTIF, 0.5, vel=80, swell=(118, 46))]
    return clip(motif, end="D4", mood="party", instrument="horn", held_vel=92, hold=0.5,
                layers=[(_shield(seed=32), MOTIF, -5.0)])


# ============================================================================= Guardian (half time, D)
def _guardian_wall() -> np.ndarray:
    """Low bowed strings build a D-major chord from the bottom up, D A D F# A D, while a
    timpani roll swells under them; the wall is held firm on D."""
    held = MOTIF + 0.62
    motif = [n("strings", p, t, held - t, vel=v, swell=(92, 124))
             for p, t, v in (("D2", 0.0, 112), ("A2", 0.22, 92), ("D3", 0.44, 108), ("F#3", 0.66, 102),
                             ("A3", 0.88, 88), ("D4", 1.10, 110))]
    motif += [n("timpani", "D2", 0.0, 0.5, vel=70)] + _timp_roll("D2", 0.6, MOTIF - 0.6, 22, 66)
    motif += [n("timpani", "D2", MOTIF, 0.6, vel=92)]
    return clip(motif, end="D", mood="party", instrument=None, slow=True, cadence_at=MOTIF, bed="harp",
                bed_db=-14.0)


def _guardian_shields() -> np.ndarray:
    """A shield wall: cellos and basses, then violas, step up into a D-major chord in
    three blocks, each set down on a timpani stroke; a roll swells into the last, held."""
    end = MOTIF + 0.62

    def block(t: float, parts) -> List[INote]:
        return [n(i, p, t, end - t, vel=v, swell=(100, 124)) for i, p, v in parts]

    motif = block(0.0, [("contrabass", "D2", 112), ("cello", "D3", 108)])
    motif += block(0.44, [("cello", "A2", 90), ("viola", "F#3", 100)])
    motif += block(0.88, [("viola", "A3", 88), ("viola", "D4", 108)])
    motif += [n("timpani", "D2", 0.0, 0.4, vel=78), n("timpani", "A2", 0.44, 0.4, vel=74),
              n("timpani", "D2", 0.88, 0.2, vel=72)]
    motif += _timp_roll("D2", 1.0, MOTIF - 1.0, 30, 72) + [n("timpani", "D2", MOTIF, 0.6, vel=94)]
    return clip(motif, end="D", mood="party", instrument=None, slow=True, cadence_at=MOTIF, bed="harp",
                bed_db=-14.0)


# ============================================================================= Damage (D)
def _dm(t: float, vel: int = 108, top: str = "F4") -> List[INote]:
    """A D-minor chord strummed down hard on the lute (``top="D4"``: the bare D A D, the
    D not struck twice: two copies of one sample 11 ms apart comb-filter)."""
    ps = ["D3", "A3", "D4"] + ([top] if top != "D4" else [])
    return roll("lute", ps, t, 0.5, vel=vel, spread=0.011)


def _damage_stab() -> np.ndarray:
    """One deep bodhran strike under a strummed D-minor stab: D (long), D, A, then D
    again, ringing out briefly. Plain and solid."""
    motif = _dm(0.0, 112) + _dm(DQ, 100) + roll("lute", ["A2", "E3", "A3"], DQ + 2 * EIGHTH, 0.1, vel=96,
                                                spread=0.01)
    motif += _dm(BAR, 106, top="D4")
    drum = _strokes("bodhran", [(0.0, 124), (BAR, 92)])
    return clip(motif, end="D", mood="enemy", instrument=None, cadence_at=BAR, layers=[(drum, 0.0, 0.0)],
                tail=False)


def _damage_strike() -> np.ndarray:
    """The dotted strike on the lute's low strings with the bodhran (D, D, A), then the
    D-minor chord strummed hard over a deep strike, left to ring."""
    motif = phrase("lute", "D3:3 D3:2 A2", vel=108, legato=0.7, seed=111)
    motif += _dm(BAR, 112) + [n("lute", "D2", BAR, 0.6, vel=96)]
    drum = _strokes("bodhran", [(0.0, 112), (DQ, 96), (DQ + 2 * EIGHTH, 84), (BAR, 126)])
    return clip(motif, end="D", mood="enemy", instrument=None, cadence_at=BAR, layers=[(drum, 0.0, 0.0)],
                tail=False)


# ============================================================================= the list
CANDIDATES = [
    info("immunity", "immunity_jig", "IMMUNITY jig",
         "The Whistle jig's dark twin: bassoon and fiddle in D minor run into a wooden stamp thump, and the "
         "bassoon droops away down a comic slide.", _immunity_jig, ["jig", "comic"]),
    info("immunity", "stamped_flat", "Stamped flat",
         "The fiddle starts the minor jig over a bassoon oom-pah; the stamp lands a bar in and both sag down "
         "to D together.", _immunity_stamp, ["jig", "comic"]),
    info("mage", "curious_peek", "Curious peek",
         "Celesta climbs D E G# A, tiptoes round the raised fourth and stops on A, harp harmonics chiming: a "
         "peek behind the curtain.", _mage_peek, ["magic", "question"]),
    info("mage", "slow_peek", "Slow peek",
         "The same lydian question at half time: celesta steps up to A and trembles there over soft harp "
         "harmonics.", _mage_slow, ["magic", "question"]),
    info("druid", "forest_call", "Forest call",
         "Our shuffle and a quick deal, then a pan flute calls up the dorian scale with a bird trill and hangs "
         "on high A over rustling leaves.", _druid_call, ["earthy", "question"]),
    info("druid", "bird_trills", "Bird trills",
         "Our shuffle, then a low pan-flute call trilling down to A, birds answering high up, left hanging on "
         "the low A.", _druid_birds, ["earthy", "question"]),
    info("cleric", "rising_harp", "Rising harp",
         "Our shuffle, then the harp climbs a D-major arpeggio and rings on high D with a soft hand bell.",
         _cleric_rise, ["gentle"]),
    info("cleric", "two_waves", "Two waves",
         "Our shuffle, then two rising harp waves over a falling bass, lifting to a ringing high D and a hand "
         "bell.", _cleric_waves, ["gentle"]),
    info("bard", "strummed_run", "Strummed run",
         "Our draw, then the lute runs up the scale into a strummed chord and skips round a turn to D.",
         _bard_run, ["tavern"]),
    info("bard", "bards_flourish", "Bard's flourish",
         "Our draw, a strummed chord and a skip, then a quick lute run up and back down to D on a last strum.",
         _bard_flourish, ["tavern"]),
    info("chanter", "plainchant_call", "Plainchant call",
         "Humming voices over a hummed drone: a plainchant call rising step by step to wait on A.",
         _chanter_call, ["voices", "question"]),
    info("chanter", "organum", "Organum",
         "Two humming voices a fourth apart, at half time over a low hum, rising to rest open on A.",
         _chanter_organum, ["voices", "question"]),
    info("reaver", "digging_cello", "Digging cello",
         "Cello digs down D A F D twice, a woodblock pick on every stroke, and stops on an open low A.",
         _reaver_dig, ["dark", "question"]),
    info("reaver", "gravedigger", "Gravedigger",
         "Cello in short heaving strokes with woodblock picks and a muffled spade thud, stopping on low A.",
         _reaver_grave, ["dark", "question"]),
    info("warrior", "double_stamp", "Double stamp",
         "Fiddle double stops stamp onto hard tabor hits, then the same an octave higher, and a last stamp on D.",
         _warrior_stamp, ["driving"]),
    info("warrior", "doubled_reel", "Doubled reel",
         "A driving fiddle reel figure with tabor, played again an octave higher, ending on a stamped D.",
         _warrior_reel, ["driving"]),
    info("paladin", "shield_fifth", "Shield fifth",
         "Two French horns hold a calm D-A fifth over a struck shield's ring, then climb to a held D.",
         _paladin_fifth, ["noble"]),
    info("paladin", "noble_call", "Noble call",
         "A calm horn call over a low horn D, landing on D as the shield is struck and rings under it.",
         _paladin_call, ["noble"]),
    info("guardian", "wall_of_strings", "Wall of strings",
         "Low bowed strings build a D-major chord from the bottom up over a swelling timpani roll, held firm.",
         _guardian_wall, ["broad", "slow"]),
    info("guardian", "shield_wall", "Shield wall",
         "Basses, cellos and violas step up into a D-major chord in three blocks on timpani strokes, held firm.",
         _guardian_shields, ["broad", "slow"]),
    info("damage", "lute_stab", "Lute stab",
         "One deep bodhran strike under a strummed D-minor stab in a dotted D D A, ringing out briefly.",
         _damage_stab, ["plain"]),
    info("damage", "dotted_strike", "Dotted strike",
         "Low lute strings and bodhran in the dotted strike, then a hard D-minor strum over a deep drum.",
         _damage_strike, ["plain"]),
]
