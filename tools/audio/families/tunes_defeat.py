"""Info pop-ups, the defeat group (docs/INFO_POPUPS.md, "Melody plan", LEITMOTIFS): the
enemy's cards (New enemy, Enemy changes, Enemy attacks, No damage, Feign death, Damage
paid, Team damage) and the kill's cards (Defeated, Exact kill!, Hydra regrows, Clean-up).

Two ideas run through the group:

  THE ENEMY MOTIF   D F E D in D minor: a rising minor third falling back through E to D,
                    on horns over a low drum. New enemy states it (a brisk horn call, or at
                    half time over doom booms); Enemy changes twists it on low strings (D
                    E-flat D C-sharp D) with a creak of wood; Enemy attacks strikes it hard
                    at half time on low brass and war drums; No damage starts it and the
                    Paladin's horn fifth smothers the drum blow; Damage paid plays it on the
                    lute in D major (D F-sharp E D), softly settled; Team damage gives it to
                    a low horn and a trombone in unison over frame drums all round.
  THE DEFEAT FLOURISH  a falling lute run down D minor (D C B-flat A G F E D) over a fading
                    timpani roll, answered in D major: Defeated. Exact kill! turns it
                    upward (a rising run, a harp glissando to high D, celesta sparkle, a
                    pipe trill); Hydra regrows lets a bassoon slither back up from D to A
                    and on to D under a hiss of shaker; Clean-up sweeps and squares the
                    cards and lets a short lute run settle on D.

Endings: every clip ends on D except the two that stand right before a payment box:
Enemy attacks' first candidate (the discard box) and Team damage (the team-discard box,
docs/INFO_POPUPS.md queue rule 5: "the defeat-step cards, each before its box: ... Team
damage (m6)") end open on A over the open A-E fifth. Enemy attacks' second candidate ends
on the "grim low D" its own brief asks for, so the owner can choose.

Every clip is built by ``_info_common.clip`` (the shared pickup, cadence bed, tail, room
and master). Damage paid bakes in the game's own discard sound as its pickup; Clean-up's
pickup is a modelled sweep of cards across the felt.

Private helpers model the struck and rubbed things no bank records: ``_creak`` (wood under
strain, stick-slip pulses through a plank's resonances), ``_sweep`` / ``_square`` (cards
swept across felt, a deck squared with two taps), ``_cloth_thump`` (a body flopping onto a
rug), ``_breath`` (a quick in-breath, held), ``_flutter`` (a card spinning through the air).
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

import numpy as np
from scipy import signal

from _info_common import (BAR, DQ, EIGHTH, MOTIF, QUARTER, SIXTEENTH, SR, A, INote, card_sound, choke, clip, info,
                          n, perc, phrase, render, roll, to_level, trill)

S = SIXTEENTH
E = EIGHTH


# ============================================================================= helpers
def _strokes(name_: str, hits: Sequence[Tuple[float, float]], lp: float = 0.0) -> np.ndarray:
    """A tavern percussion part: ``perc`` strokes at (time, velocity). Velocities are
    rendered in steps of 8 and the rest made up in gain (one bank render per step)."""
    x = np.zeros(A.n_of(0.1))
    for t, v in hits:
        q = int(min(127, max(8, 8 * math.ceil(v / 8.0))))
        x = A.mix_at(x, perc(name_, q) * (v / q), t)
    return A.lowpass(x, lp, 2) if lp else x


def _timp_roll(pitch: str, start: float, dur: float, v0: float, v1: float, rate: float = 0.046,
               seed: int = 0) -> List[INote]:
    """A timpani roll: single strokes every ``rate`` s, a little uneven, from ``v0`` to ``v1``."""
    rng = np.random.default_rng(seed)
    k = max(2, int(round(dur / rate)))
    out = []
    for i in range(k):
        t = start + i * rate + (float(rng.uniform(-0.004, 0.004)) if i else 0.0)
        v = (v0 + (v1 - v0) * i / (k - 1)) * (0.9 if i % 2 else 1.0)
        out.append(n("timpani", pitch, max(0.0, t), rate * 0.9, vel=int(np.clip(round(v), 1, 127))))
    return out


def _reson(x: np.ndarray, f: float, t60: float) -> np.ndarray:
    """A two-pole resonator ringing at ``f`` for ``t60`` seconds."""
    w = 2 * math.pi * f / SR
    r = 0.001 ** (1.0 / (t60 * SR))
    return signal.lfilter([math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], x)


def _env(d: float, pts: Sequence[Tuple[float, float]]) -> np.ndarray:
    t = np.arange(A.n_of(d)) / SR
    return np.interp(t, [p[0] for p in pts], [p[1] for p in pts])


def _creak(d: float = 0.6, seed: int = 0) -> np.ndarray:
    """Wood creaking under strain (a door, a chair, the table): stick-slip pulses whose rate
    wanders, ringing a plank's resonances, swelling in and out."""
    rng = np.random.default_rng(seed)
    t = np.arange(A.n_of(d)) / SR
    rate = np.interp(t, [0, 0.35 * d, 0.75 * d, d], [70, 150, 110, 60])
    wob = A.lowpass(rng.standard_normal(len(t)), 9, 1)
    rate = rate * (1 + 0.08 * wob / (np.max(np.abs(wob)) or 1.0))
    ph = np.cumsum(rate) / SR
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0] + 1
    idx = np.clip(idx + rng.integers(-15, 16, len(idx)), 0, len(t) - 1)
    pulses = np.zeros(len(t))
    pulses[idx] = rng.uniform(0.5, 1.0, len(idx))
    modes = [(310, 1.0, 0.06), (520, 0.8, 0.045), (860, 0.6, 0.035), (1330, 0.4, 0.025), (2050, 0.2, 0.02)]
    y = sum(g * _reson(pulses, f, T) for f, g, T in modes)
    y = y * _env(d, [(0, 0), (0.08 * d, 0.7), (0.4 * d, 1.0), (0.8 * d, 0.6), (d, 0.0)])
    return A.lowpass(y, 3000, 2)


def _sweep(d: float = 0.26, seed: int = 0) -> np.ndarray:
    """Played cards swept together across the felt: a soft, grainy paper rub that grows
    and dies, its top dulled by the cloth."""
    x = A.paper(d, 500, 3600, seed=seed, grain=0.5)
    x = x * _env(d, [(0, 0), (0.25 * d, 0.7), (0.7 * d, 1.0), (d, 0.0)])
    return A.lowpass(x, 3200, 2)


def _square() -> np.ndarray:
    """The swept stack squared: its edge tapped twice on the table through the felt (a
    dull wooden knock and the cards' soft slap)."""
    knock = A.lowpass(perc("woodblock", 70), 1100, 2)
    slap = A.lowpass(card_sound("play"), 2600, 2)
    one = A.mix_at(to_level(knock, -30.0), to_level(slap, -32.0), 0.0)
    x = A.mix_at(np.zeros(A.n_of(0.3)), one, 0.0)
    return A.mix_at(x, 0.75 * one, 0.085)


def _cloth_thump(seed: int = 0) -> np.ndarray:
    """A body flopping onto a rug: a muffled frame-drum thud and a short swish of cloth."""
    thud = choke(A.lowpass(perc("frame_drum", 72), 520, 2), 0.05, 0.22)
    d = 0.2
    swish = A.bandpass(A.noise(d, "pink", seed), 350, 2400) * _env(d, [(0, 0), (0.02, 1.0), (0.07, 0.5), (d, 0)])
    return A.mix_at(to_level(thud, -28.0), to_level(swish, -38.0), 0.0)


def _breath(d: float = 0.24, seed: int = 0) -> np.ndarray:
    """A quick in-breath, then held: soft noise through a mouth's two resonances, rising and
    stopping short."""
    x = A.bandpass(A.noise(d, "pink", seed), 400, 3200)
    x = 0.6 * A.peak_eq(x, 1150, 8.0, 3.0) + 0.4 * A.peak_eq(x, 2300, 6.0, 4.0)
    return x * _env(d, [(0, 0), (0.7 * d, 1.0), (0.9 * d, 0.6), (d, 0.0)])


def _flutter(d: float = 0.3, seed: int = 0) -> np.ndarray:
    """A card spinning up through the air: a rising swish of air beating as it turns."""
    t = np.arange(A.n_of(d)) / SR
    x = A.sweep_lowpass(A.highpass(A.noise(d, "pink", seed), 600, 2), 1200, 4200, 24)
    spin = 1 + 0.45 * np.sin(2 * math.pi * 20 * t)
    return x * spin * _env(d, [(0, 0), (0.6 * d, 1.0), (0.9 * d, 0.3), (d, 0)])


# the defeat flourish: a falling run down D minor in sixteenths, landing on D4 (one bar)
_FALL = "D5:0.5 C5:0.5 Bb4:0.5 A4:0.5 G4:0.5 F4:0.5 E4 D4:2"


# ============================================================================= New enemy (D)
def _new_horn_call() -> np.ndarray:
    """Two horns in octaves call the enemy motif, D F E D, then drop to low A and return to
    D; a timpani and a war drum mark the beats."""
    hi = phrase("horn", "D4:3 F4:2 E4 D4:3 A3:3", vel=94, legato=0.97, accent=10, seed=301)
    lo = phrase("horn", "D3:3 F3:2 E3 D3:3 A2:3", vel=78, legato=0.97, accent=8, seed=302, pan=-0.2)
    lo += [n("horn", "D3", MOTIF, 0.46, vel=80, pan=-0.2, swell=(118, 46))]
    drums = [n("timpani", "D3", 0.0, 0.4, vel=100), n("timpani", "D3", BAR, 0.4, vel=92),
             n("timpani", "A2", BAR + DQ, 0.3, vel=80), n("timpani", "D3", MOTIF, 0.5, vel=96)]
    war = _strokes("war_drum", [(0.0, 112), (BAR, 100), (MOTIF, 96)])
    return clip(hi + lo + drums, end="D", mood="enemy", instrument="horn", held_vel=98,
                layers=[(war, 0.0, -7.0)])


def _new_doom_horns() -> np.ndarray:
    """Half time: two deep booms (timpani and bass drum) under low strings in D minor, the
    horns and a trombone growl D F E in unison, and a third boom lands the low D."""
    brass = phrase("horn", "D3:3 F3:2 E3", slow=True, vel=100, legato=0.98, accent=10, seed=311)
    brass += phrase("trombone", "D3:3 F3:2 E3", slow=True, vel=82, legato=0.98, accent=8, seed=312)
    brass += [n("trombone", "D3", MOTIF, 0.66, vel=84, swell=(118, 46))]
    strings = [n("cello", "D3", 0.0, MOTIF + 0.6, vel=86, swell=(60, 110)),
               n("contrabass", "D2", 0.0, MOTIF + 0.6, vel=72, swell=(60, 104)),
               n("strings", "F3", 0.05, MOTIF + 0.5, vel=62, swell=(50, 96)),
               n("strings", "A3", 0.05, MOTIF + 0.5, vel=58, swell=(50, 92))]
    timp = [n("timpani", "D3", 0.0, 0.5, vel=112), n("timpani", "D3", 2 * DQ, 0.5, vel=96),
            n("timpani", "D3", MOTIF, 0.6, vel=104)]
    boom = _strokes("bass_drum", [(0.0, 124), (2 * DQ, 104), (MOTIF, 112)])
    return clip(brass + strings + timp, end="D", mood="enemy", instrument="horn", slow=True, held_vel=100,
                layers=[(boom, 0.0, -5.0)], bed_db=-14.0)


# ============================================================================= Enemy changes (D)
def _enemy_shift() -> np.ndarray:
    """The enemy motif on cello and double bass, D F E, then a twisting turn D E-flat D
    C-sharp back to D, while old wood creaks: the enemy changes shape. A viola shadows the
    cello an octave up, softly, so the twist carries on a phone's small speaker."""
    tune = "D3:3 F3:2 E3 D3 Eb3 D3 C#3:3"
    cello = phrase("cello", tune, vel=92, legato=1.0, accent=10, seed=321)
    viola = phrase("viola", "D4:3 F4:2 E4 D4 Eb4 D4 C#4:3", vel=58, legato=1.0, accent=6, seed=324)
    viola += [n("viola", "D4", MOTIF, 0.46, vel=56, swell=(110, 40))]
    bass = phrase("contrabass", "D2:3 F2:2 E2 D2 Eb2 D2 C#2:3", vel=66, legato=1.0, accent=6, seed=322)
    bass += [n("contrabass", "D2", MOTIF, 0.5, vel=64)]
    pizz = [n("pizzicato", "D3", 0.0, 0.2, vel=84), n("pizzicato", "D3", BAR, 0.2, vel=74)]
    return clip(cello + viola + bass + pizz, end="D", mood="enemy", instrument="cello", held_vel=94,
                layers=[(_creak(0.62, 323), BAR - 0.04, -9.0)])


# ============================================================================= Enemy attacks (A, then D)
def _attack_brass() -> np.ndarray:
    """Half time, before the discard box: the whole low brass and a war drum strike the
    enemy motif on a heavy downbeat, D F E, then hold an open low A over the bare fifth:
    what will you pay?"""
    tb = phrase("trombone", "D3:3 F3:2 E3", slow=True, vel=112, legato=0.96, accent=10, seed=331)
    hn = phrase("horn", "D4:3 F4:2 E4", slow=True, vel=100, legato=0.96, accent=10, seed=332)
    low = [n("tuba", "D2", 0.0, 0.6, vel=108), n("tuba", "A1", MOTIF, 0.66, vel=96, swell=(118, 46)),
           n("horn", "E4", MOTIF, 0.66, vel=84, swell=(118, 46)),
           n("timpani", "D3", 0.0, 0.5, vel=118), n("timpani", "A2", MOTIF, 0.6, vel=100)]
    war = _strokes("war_drum", [(0.0, 127), (2 * DQ, 96), (2 * DQ + 4 * E, 88), (MOTIF, 112)])
    boom = _strokes("bass_drum", [(0.0, 120)])
    return clip(tb + hn + low, end="A2", mood="enemy", instrument="trombone", slow=True, held_vel=104,
                layers=[(war, 0.0, -4.0), (boom, 0.0, -8.0)], bed_db=-14.0)


def _attack_war_drums() -> np.ndarray:
    """Half time: a war drum crashes in with the low brass on D, the horns climb D F E over
    a drum roll that gathers, and everything lands on a grim low D."""
    hn = phrase("horn", "D4:3 F4:2 E4", slow=True, vel=96, legato=0.96, accent=10, seed=341)
    hn += phrase("horn", "D3:3 F3:2 E3", slow=True, vel=80, legato=0.96, accent=8, seed=342, pan=-0.2)
    low = [n("trombone", "D3", 0.0, 0.55, vel=110), n("tuba", "D2", 0.0, 0.55, vel=110),
           n("tuba", "D2", MOTIF, 0.66, vel=112, swell=(118, 46)),
           n("horn", "D3", MOTIF, 0.66, vel=92, pan=-0.2, swell=(118, 46)),
           n("timpani", "D3", 0.0, 0.5, vel=120), n("timpani", "D3", MOTIF, 0.6, vel=122)]
    low += _timp_roll("A2", 2 * DQ + 0.1, MOTIF - 2 * DQ - 0.14, 40, 96, seed=343)
    war = _strokes("war_drum", [(0.0, 127), (2 * DQ, 92), (MOTIF, 127)])
    gather = _strokes("frame_drum", [(2 * DQ + i * S, 40 + 6 * i) for i in range(11)])
    return clip(hn + low, end="D3", mood="enemy", instrument="trombone", slow=True, held_vel=112,
                layers=[(war, 0.0, -3.0), (gather, 0.0, -12.0)], bed_db=-14.0)


# ============================================================================= No damage (D)
def _shielded() -> np.ndarray:
    """The enemy motif starts low on trombone, D F E; its drum blow lands muffled as the
    Paladin's two horns swell up on a D-A fifth; then the lute strums a relieved D major."""
    motif = phrase("trombone", "D3:3 F3:2 E3:0.6", vel=96, legato=0.9, accent=8, seed=351)
    motif += [n("horn", "D4", DQ + 2 * E, 0.62, vel=86, swell=(50, 118)),
              n("horn", "A4", DQ + 2 * E + 0.02, 0.6, vel=82, swell=(50, 114))]
    motif += roll("lute", ["D3", "A3", "D4", "F#4", "A4"], BAR + DQ, 1.0, vel=94, spread=0.022)
    motif += [n("timpani", "D3", 0.0, 0.3, vel=84)]
    blow = choke(A.lowpass(perc("war_drum", 110), 380, 2), 0.04, 0.12)
    return clip(motif, end="D", mood="party", instrument=None, cadence_at=BAR + DQ,
                layers=[(blow, BAR, -9.0)])


# ============================================================================= Feign death (D)
def _feign_death() -> np.ndarray:
    """A fiddle droops down a comic octave slide, the player flops onto the rug with a soft
    thump, gasps a breath and holds it ... then one quiet lute note."""
    fid = [n("violin", "A5", 0.0, 0.12, vel=96),
           n("violin", "A5", 0.12, 0.42, vel=92, bend=(0.0, -12.0), swell=(110, 46))]
    # the lute note is quiet: a layer set under the fiddle (as the held note it came out
    # 2 dB over the fiddle, whatever its velocity: a pluck after the held breath startled)
    lute = render([n("lute", "D4", 0.0, 0.5, vel=78)])
    return clip(fid, end="D4", mood="party", instrument=None, cadence_at=MOTIF, hold=0.5,
                bed=None, tail_db=-17.0,
                layers=[(_cloth_thump(361), 0.56, -5.0), (_breath(0.24, 362), 0.74, -16.0),
                        (lute, MOTIF, -7.0)])


# ============================================================================= Damage paid (D)
def _damage_paid() -> np.ndarray:
    """Our discard sound, then the lute plays the enemy motif softly in D major (D F-sharp
    E D), steps down to A and up through C-sharp to settle on D: the blow absorbed."""
    tune = phrase("lute", "D4:3 F#4:2 E4 D4:3 A3:2 C#4", vel=78, legato=1.0, accent=8, seed=371)
    bass = [n("lute", "D3", 0.0, 0.62, vel=60), n("lute", "A2", BAR, 0.62, vel=56)]
    return clip(tune + bass, end="D", mood="party", instrument="lute", held_vel=80, pickup="discard",
                bed_db=-13.0)


# ============================================================================= Team damage (A)
def _team_damage() -> np.ndarray:
    """Frame drums and bodhrans from all round the table in a gathering 6/8 gallop, a low
    horn with a trombone in unison on the enemy motif (D F E D, then E F), and everyone
    braces on an open A. (Two horn lines from the one sample a few ms apart comb-filter
    into a hollow, phasing tone: the second voice is a trombone.)"""
    tune = "D3:3 F3:2 E3 D3:3 E3:2 F3"
    horns = phrase("horn", tune, vel=92, legato=0.98, accent=10, seed=381, pan=-0.3)
    horns += phrase("trombone", tune, vel=76, legato=0.98, accent=8, seed=382, pan=0.3)
    horns += [n("horn", "A3", MOTIF, 0.48, vel=86, pan=0.3, swell=(118, 46))]
    bod = _strokes("bodhran", [(0.0, 116), (DQ, 98), (BAR, 116), (BAR + DQ, 106)])
    frame = _strokes("frame_drum", [(E, 64), (2 * E, 70), (DQ + E, 70), (DQ + 2 * E, 76), (BAR + E, 78),
                                    (BAR + 2 * E, 84), (BAR + DQ + E, 90), (BAR + DQ + 2 * E, 100)])
    war = _strokes("war_drum", [(0.0, 104), (BAR, 108)])
    tabor = _strokes("tabor", [(DQ + 2 * E, 50), (BAR + DQ + 1.5 * E, 54), (BAR + DQ + 2 * E, 62)])
    return clip(horns, end="A3", mood="enemy", instrument="horn", held_vel=92,
                layers=[(bod, 0.0, -5.0), (frame, 0.0, -8.0), (war, 0.0, -8.0), (tabor, 0.0, -14.0)])


# ============================================================================= Defeated (D)
def _defeated_topple() -> np.ndarray:
    """The defeat flourish: a lute run tumbles down D minor over a fading timpani roll, a
    D-minor strum, then the lute turns it to a ringing D major."""
    run = phrase("lute", _FALL, vel=94, legato=1.25, accent=6, seed=391)
    chords = roll("lute", ["D3", "A3", "D4", "F4"], BAR, DQ, vel=90, spread=0.014)
    chords += roll("lute", ["D3", "A3", "D4", "F#4", "A4", "D5"], BAR + DQ, 1.2, vel=100, spread=0.016)
    timp = _timp_roll("D3", 0.0, 0.92, 88, 26, seed=392)
    return clip(run + chords + timp, end="D", mood="party", instrument=None, cadence_at=BAR + DQ, hold=0.5)


def _defeated_horns() -> np.ndarray:
    """The lute run tumbles down D minor over the fading drum roll; two hunting horns answer
    in D major, D D A, and ring out on D in octaves."""
    run = phrase("lute", _FALL, vel=90, legato=1.25, accent=6, seed=401)
    hi = phrase("horn", "D4:2 D4 A4:3", at=BAR, vel=96, legato=0.95, accent=8, seed=402)
    lo = phrase("horn", "A3:2 A3 F#4:3", at=BAR, vel=84, legato=0.95, accent=6, seed=403, pan=-0.2)
    lo += [n("horn", "D4", MOTIF, 0.46, vel=80, pan=-0.2, swell=(118, 46))]
    timp = _timp_roll("D3", 0.0, 0.62, 84, 30, seed=404) + [n("timpani", "D3", BAR, 0.3, vel=84),
                                                            n("timpani", "A2", MOTIF, 0.5, vel=80)]
    return clip(run + hi + lo + timp, end="D5", mood="party", instrument="horn", held_vel=96)


# ============================================================================= Exact kill! (D)
def _exact_glissando() -> np.ndarray:
    """The defeat flourish turned upward: a lute run climbs, a harp glissando sweeps up to
    high D, celesta sparkles over it and a pipe trills on D and holds it, bright."""
    run = phrase("lute", "D4:0.5 E4:0.5 F#4:0.5 G4:0.5 A4:0.5 B4:0.5", vel=92, legato=1.3, accent=6, seed=411)
    gl = ["A4", "B4", "C#5", "D5", "E5", "F#5", "G5", "A5", "B5", "C#6", "D6"]
    st = 0.027
    harp = [n("harp", p, BAR - st * (len(gl) - 1) + st * i, 0.7, vel=66 + 3 * i) for i, p in enumerate(gl)]
    harp += [n("harp", "D3", BAR, 1.0, vel=86), n("harp", "A3", BAR + 0.012, 1.0, vel=74)]
    cel = [n("celesta", p, BAR + i * S, 0.5, vel=88 - 5 * i) for i, p in enumerate(["D6", "F#6", "A6", "D7"])]
    cel += [n("glockenspiel", "D7", BAR, 0.5, vel=52)]
    pipe = trill("pipe", "D6", "E6", BAR + DQ, 0.3, vel=82, rate=0.05)
    tamb = _strokes("tambourine", [(BAR, 70)])
    return clip(run + harp + cel + pipe, end="D6", mood="party", instrument="pipe", held_vel=88,
                layers=[(tamb, 0.0, -14.0)])


def _exact_golden_card() -> np.ndarray:
    """A lute arpeggio leaps up and strums D major; the fallen enemy's card flutters through
    the air and lands on the deck with a golden ring of celesta, gold dust rising after."""
    run = phrase("lute", "D4:0.5 F#4:0.5 A4:0.5 D5:0.5 F#5:0.5 A5:0.5", vel=88, legato=1.4, accent=6, seed=421)
    run += roll("lute", ["D3", "A3", "D4", "F#4", "A4", "D5"], DQ, 0.9, vel=100, spread=0.012)
    ding = [n("celesta", "D6", BAR, 0.6, vel=104), n("glockenspiel", "A6", BAR, 0.5, vel=58),
            n("harp", "D5", BAR, 0.8, vel=60), n("harp", "A4", BAR, 0.8, vel=52)]
    dust = [n("celesta", p, BAR + E + i * S, 0.35, vel=70 - 4 * i)
            for i, p in enumerate(["E6", "F#6", "A6", "B6", "D7"])]
    held = roll("lute", ["D3", "D4", "F#4", "A4", "D5"], MOTIF, 0.6, vel=88, spread=0.016)
    land = A.lowpass(card_sound("play"), 5000, 2)
    tabor = _strokes("tabor", [(DQ, 70), (MOTIF, 60)])
    return clip(run + ding + dust + held, end="D", mood="party", instrument=None,
                layers=[(_flutter(0.3, 422), BAR - 0.3, -16.0), (land, BAR - 0.004, -8.0), (tabor, 0.0, -14.0)])


# ============================================================================= Hydra regrows (D)
def _hydra_regrows() -> np.ndarray:
    """The defeat flourish falls, then a bassoon slithers back up from low D to A, and
    again from A to D, under a rising hiss of shaker: the heads grow back."""
    run = phrase("lute", _FALL, vel=90, legato=1.25, accent=6, seed=431)
    timp = _timp_roll("D3", 0.0, 0.5, 80, 30, seed=432)
    # each slither glides up in a quarter, then the new head holds its note
    glide = QUARTER - 0.02
    bsn = [n("bassoon", "A3", BAR, glide, vel=96, bend=(-7.0, 0.0)),
           n("bassoon", "A3", BAR + glide, DQ - glide - 0.01, vel=92),
           n("bassoon", "D4", BAR + DQ, glide, vel=96, bend=(-5.0, 0.0)),     # from the A, up to D
           n("bassoon", "D4", BAR + DQ + glide, MOTIF - BAR - DQ - glide + 0.48, vel=94, swell=(112, 46))]
    hiss = _strokes("shaker", [(BAR + i * S, 34 + 6 * i) for i in range(12)])
    hiss = A.mix_at(hiss, _strokes("cabasa", [(BAR + DQ - 0.02, 70)]), 0.0)
    return clip(run + timp + bsn, end="D", mood="enemy", instrument=None, cadence_at=MOTIF,
                layers=[(hiss, 0.0, -13.0)])


# ============================================================================= Clean-up (D)
def _cleanup() -> np.ndarray:
    """Cards swept across the felt and squared with two taps, then a short lute run steps
    down B A G F-sharp E D, turns on C-sharp and settles on D: the table tidied."""
    sweep = _sweep(0.26, 441)
    lute = phrase("lute", "B4 A4 G4 F#4 E4 D4 C#4", at=2 * E, vel=80, legato=1.05, accent=6, seed=442)
    lute += [n("lute", "D3", DQ, 0.6, vel=58), n("lute", "A2", BAR, 0.33, vel=52)]
    return clip(lute, end="D", mood="party", instrument="lute", held_vel=84, cadence_at=BAR + DQ,
                pickup=(sweep, 2 * E), pickup_db=-8.0, layers=[(_square(), 0.0, -7.0)])


# ============================================================================= the list
CANDIDATES = [
    info("new_enemy", "horn_call", "Horn call",
         "Two horns call the enemy motif, D F E D, over timpani and war drum, dip to low A and land firmly on "
         "D: dark and firm.", _new_horn_call, ["enemy", "horn"]),
    info("new_enemy", "doom_horns", "Doom horns",
         "Half time: deep booms under low strings in D minor while horns and trombone growl D F E, and a third "
         "boom lands the low D.", _new_doom_horns, ["enemy", "dark"]),
    info("enemy_shift", "twisting_strings", "Twisting strings",
         "Cello and double bass play the enemy motif and twist it (D E-flat D C-sharp D) while old wood "
         "creaks: the enemy changes shape.", _enemy_shift, ["enemy", "strings"]),
    info("enemy_attack", "brass_strike", "Brass strike",
         "Half time: the low brass and a war drum strike the enemy motif on a heavy downbeat, then hold an "
         "open low A: what will you pay?", _attack_brass, ["enemy", "brass", "question"]),
    info("enemy_attack", "war_drums", "War drums",
         "Half time: a war drum crashes in with the brass, horns climb D F E over a gathering roll, and all "
         "land on a grim low D.", _attack_war_drums, ["enemy", "drums"]),
    info("shielded", "horn_shield", "Horn shield",
         "The enemy motif starts on trombone; its drum blow lands muffled under the Paladin's horn fifth, "
         "then the lute strums a relieved D major.", _shielded, ["relief", "horn"]),
    info("feign_death", "playing_dead", "Playing dead",
         "A fiddle droops down a comic slide, a soft thump onto the rug, a held breath, then one quiet lute "
         "note.", _feign_death, ["comic", "quiet"]),
    info("damage_paid", "blow_absorbed", "Blow absorbed",
         "Our discard sound, then the lute plays the enemy motif softly in D major and settles on D.",
         _damage_paid, ["lute", "soft"]),
    info("team_damage", "everyone_braces", "Everyone braces",
         "Frame drums from all round the table gallop under a low horn and trombone in unison on the enemy motif, "
         "then hold an open A: brace!", _team_damage, ["enemy", "drums", "question"]),
    info("defeated", "lute_topple", "Lute topple",
         "A lute run tumbles down D minor over a fading timpani roll, a minor strum, then a ringing D-major "
         "chord.", _defeated_topple, ["lute", "flourish"]),
    info("defeated", "horns_answer", "Horns answer",
         "The lute run tumbles down D minor, then two hunting horns answer D D A in D major and ring out on "
         "D.", _defeated_horns, ["lute", "horn"]),
    info("exact_kill", "golden_glissando", "Golden glissando",
         "A lute run climbs, a harp glissando sweeps up to high D with a celesta sparkle, and a pipe trills "
         "and holds the D: bright.", _exact_glissando, ["bright", "harp"]),
    info("exact_kill", "golden_card", "Golden card",
         "A lute arpeggio leaps into a D-major strum; the enemy's card flutters onto your deck with a golden "
         "celesta ring and rising sparkle.", _exact_golden_card, ["bright", "lute"]),
    info("hydra_regrows", "heads_regrow", "Heads regrow",
         "The lute run falls, then a bassoon slithers back up from D to A and on to D under a rising hiss of "
         "shaker.", _hydra_regrows, ["enemy", "comic"]),
    info("cleanup", "table_tidied", "Table tidied",
         "Cards swept across the felt and squared with two taps, then a short lute run steps down and "
         "settles on D.", _cleanup, ["lute", "cards"]),
]
