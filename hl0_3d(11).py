"""
HALF-LIFE 0 — OpenGL 3D Prototype
W/S = move forward/back  |  A/D = turn
Controller: 8BitDo Pro 2 (left stick or D-pad) / Zero 2 (D-pad)
Final target: Source SDK — this is logic/feel prototype only.
"""

import pygame
from pygame.locals import *
try:
    from OpenGL.GL import *
    from OpenGL.GLU import *
except ImportError:
    print("Missing: pip install PyOpenGL PyOpenGL_accelerate")
    import sys; sys.exit(1)

import sys, math, random, os, json

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ── Asset paths — look next to the script first, then CWD ────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def asset(name):
    # Also try timestamp-prefixed versions (as uploaded)
    # and common alternate names
    candidates = [name]
    # Add common alternates
    stem = name.replace(".png","").replace(".mp3","")
    ext  = ".png" if name.endswith(".png") else ".mp3"
    alt_map = {
        "logo_valve":   ["valve", "1774105348825_image"],
        "logo_tcf":     ["tcf",   "1774105358920_image"],
        "logo_hl0":     ["hl0",   "1774105379561_image", "halflife0"],
        "logo_loading": ["loading","1774105419858_image"],
        "AutomationBuilding": ["automationbuilding", "automation_building", "bg"],
        "01_Hazardous_Environments": ["hazardous_environments","01_hazardous_environments","music"],
    }
    for alt in alt_map.get(stem, []):
        candidates.append(alt + ext)

    for d in (_SCRIPT_DIR, os.getcwd()):
        for c in candidates:
            p = os.path.join(d, c)
            if os.path.exists(p): return p
    return None

def list_dir_assets():
    """Print files found next to the script — helps debug missing assets."""
    print("[ASSET] Scanning for files:")
    for d in (_SCRIPT_DIR, os.getcwd()):
        files = [f for f in os.listdir(d)
                 if f.lower().endswith(('.png','.jpg','.mp3','.ogg','.wav'))]
        if files:
            for f in sorted(files):
                print(f"  {f}")
            return
    print("  (none found)")

# ── GL texture loader ─────────────────────────────────────────────────────────
def load_gl_texture(path):
    """Load a PNG/JPG as an OpenGL texture. Returns tex id or None."""
    if path is None: return None
    try:
        surf = pygame.image.load(path).convert_alpha()
        w, h = surf.get_size()
        data = pygame.image.tostring(surf, "RGBA", True)
        tex  = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)
        return tex, w, h
    except Exception as e:
        print(f"[ASSET] Failed to load texture {path}: {e}")
        return None

def draw_fullscreen_tex(tex_info, alpha=1.0, fit="fill"):
    """Blit a GL texture fullscreen (letterboxed or stretched)."""
    if tex_info is None: return
    tex, iw, ih = tex_info
    # Compute rect to maintain aspect ratio (fit="fill" crops, "fit" letterboxes)
    img_ratio = iw / ih
    scr_ratio = W  / H
    if fit == "fill":
        if img_ratio > scr_ratio:
            dh = H; dw = int(H * img_ratio)
        else:
            dw = W; dh = int(W / img_ratio)
    else:
        if img_ratio > scr_ratio:
            dw = W; dh = int(W / img_ratio)
        else:
            dh = H; dw = int(H * img_ratio)
    ox = (W - dw) // 2; oy = (H - dh) // 2

    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    glOrtho(0, W, 0, H, -1, 1)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, tex)
    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(1, 1, 1, alpha)
    glBegin(GL_QUADS)
    glTexCoord2f(0,0); glVertex2f(ox,       oy      )
    glTexCoord2f(1,0); glVertex2f(ox+dw,    oy      )
    glTexCoord2f(1,1); glVertex2f(ox+dw,    oy+dh   )
    glTexCoord2f(0,1); glVertex2f(ox,       oy+dh   )
    glEnd()
    glDisable(GL_BLEND); glDisable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW);  glPopMatrix()

def draw_centered_tex(tex_info, cx, cy, scale=1.0, alpha=1.0):
    """Draw a texture centered at (cx,cy) in screen coords, scaled."""
    if tex_info is None: return
    tex, iw, ih = tex_info
    dw = int(iw * scale); dh = int(ih * scale)
    ox = cx - dw//2;      oy = cy - dh//2
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    glOrtho(0, W, 0, H, -1, 1)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, tex)
    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(1, 1, 1, alpha)
    glBegin(GL_QUADS)
    glTexCoord2f(0,0); glVertex2f(ox,    oy   )
    glTexCoord2f(1,0); glVertex2f(ox+dw, oy   )
    glTexCoord2f(1,1); glVertex2f(ox+dw, oy+dh)
    glTexCoord2f(0,1); glVertex2f(ox,    oy+dh)
    glEnd()
    glDisable(GL_BLEND); glDisable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW);  glPopMatrix()

# ── Window ────────────────────────────────────────────────────────────────────
W, H   = 1280, 720
FPS    = 60
FOV    = 75.0
NEAR   = 0.05
FAR    = 50.0

# ── Audio init — pre_init MUST come before pygame.init() ─────────────────────
# Stereo (2ch) required for Bluetooth on Windows — mono gets silently dropped.
# Buffer 2048 gives Bluetooth enough latency headroom.
RATE      = 44100
CHANNELS  = 2
_AUDIO_OK = False
try:
    pygame.mixer.pre_init(RATE, -16, CHANNELS, 2048)
except Exception:
    pass

pygame.init()

try:
    if not pygame.mixer.get_init():
        pygame.mixer.init(RATE, -16, CHANNELS, 2048)
    _info = pygame.mixer.get_init()
    _AUDIO_OK = (_info is not None)
    print(f"[AUDIO] OK — {_info}")
except Exception as e:
    print(f"[AUDIO] FAIL — {e}")

# ── Sound Engine — all audio generated procedurally via numpy ─────────────────
class SoundEngine:
    """
    Generates all game audio from scratch — no external files.
    Stereo output for Bluetooth/Windows compatibility.
    Falls back silently if no audio device.
    """
    def __init__(self):
        self._cache   = {}
        self._drone   = None
        self._transit = None
        self.ok       = _AUDIO_OK and HAS_NUMPY

    def _stereo(self, mono):
        """Convert mono int16 array to stereo by duplicating channel."""
        s = np.clip(mono, -32767, 32767).astype(np.int16)
        return np.column_stack([s, s])

    def _make(self, key, fn):
        if key not in self._cache and self.ok:
            try:
                arr  = fn()
                arr  = self._stereo(arr)
                snd  = pygame.sndarray.make_sound(arr)
                self._cache[key] = snd
            except Exception as e:
                print(f"[AUDIO] build '{key}' failed: {e}")
                self._cache[key] = None
        return self._cache.get(key)

    def _sine(self, freq, dur, amp=0.5, fade=0.01):
        n   = int(RATE * dur)
        t   = np.linspace(0, dur, n, endpoint=False)
        wav = np.sin(2 * np.pi * freq * t) * amp * 32767
        f   = int(RATE * fade)
        if f > 0 and f < n:
            wav[:f]  *= np.linspace(0, 1, f)
            wav[-f:] *= np.linspace(1, 0, f)
        return wav

    def _mix(self, *waves):
        length = max(len(w) for w in waves)
        out    = np.zeros(length)
        for w in waves:
            out[:len(w)] += w
        return out / len(waves)

    # ── CP Violation drone  ──────────────────────────────────────────────────
    # Layered detuned sines: 55, 55.3, 110, 165, 220 Hz with slow tremolo
    def _build_drone(self):
        dur = 4.0
        n   = int(RATE * dur)
        t   = np.linspace(0, dur, n, endpoint=False)
        trem = 0.85 + 0.15 * np.sin(2 * np.pi * 0.35 * t)
        w  = (np.sin(2*np.pi*55.0*t) * 0.40
            + np.sin(2*np.pi*55.3*t) * 0.25
            + np.sin(2*np.pi*110.0*t)* 0.20
            + np.sin(2*np.pi*165.0*t)* 0.10
            + np.sin(2*np.pi*220.0*t)* 0.06
            + np.sin(2*np.pi*27.5*t) * 0.15)
        w  *= trem
        # fade in/out for seamless loop
        f   = int(RATE * 0.08)
        w[:f]  *= np.linspace(0, 1, f)
        w[-f:] *= np.linspace(1, 0, f)
        return (w * 32767 * 0.55).astype(np.int16)

    # ── Black Mesa Transit chime — pentatonic two-note ding ──────────────────
    def _build_transit_chime(self):
        def ding(freq, dur, amp=0.6):
            n = int(RATE * dur)
            t = np.linspace(0, dur, n, endpoint=False)
            env = np.exp(-t * 4.5)
            return np.sin(2*np.pi*freq*t) * env * amp
        a  = ding(880, 0.8)
        b  = ding(1320, 0.8)
        silence = np.zeros(int(RATE * 0.25))
        clip = np.concatenate([a, silence, b, np.zeros(int(RATE*1.5))])
        return (clip * 32767).astype(np.int16)

    # ── Boot power-on hum ────────────────────────────────────────────────────
    def _build_boot_hum(self):
        dur = 2.5
        n   = int(RATE * dur)
        t   = np.linspace(0, dur, n, endpoint=False)
        freq_sweep = np.linspace(40, 120, n)
        w  = np.sin(2*np.pi * np.cumsum(freq_sweep/RATE))
        w += np.sin(2*np.pi * np.cumsum(freq_sweep*2/RATE)) * 0.3
        env = np.concatenate([
            np.linspace(0, 1, int(n*0.3)),
            np.ones(int(n*0.4)),
            np.linspace(1, 0, n - int(n*0.3) - int(n*0.4))
        ])
        env = env[:n]
        return (w * env * 32767 * 0.7).astype(np.int16)

    # ── Menu tick ────────────────────────────────────────────────────────────
    def _build_tick(self):
        n = int(RATE * 0.045)
        t = np.linspace(0, 0.045, n, endpoint=False)
        w = np.sin(2*np.pi*1200*t) * np.exp(-t*120) * 0.6
        return (w * 32767).astype(np.int16)

    # ── Menu select ──────────────────────────────────────────────────────────
    def _build_select(self):
        n = int(RATE * 0.12)
        t = np.linspace(0, 0.12, n, endpoint=False)
        w = (np.sin(2*np.pi*900*t) * 0.5
           + np.sin(2*np.pi*1800*t) * 0.25) * np.exp(-t*30)
        return (w * 32767).astype(np.int16)

    # ── Document scan chirp ──────────────────────────────────────────────────
    def _build_scan(self):
        dur = 0.35
        n   = int(RATE * dur)
        t   = np.linspace(0, dur, n, endpoint=False)
        f   = np.linspace(400, 1800, n)
        w   = np.sin(2*np.pi * np.cumsum(f/RATE))
        env = np.exp(-t * 8)
        return (w * env * 32767 * 0.55).astype(np.int16)

    # ── Xen bleed stab ───────────────────────────────────────────────────────
    def _build_xen(self):
        dur = 0.7
        n   = int(RATE * dur)
        t   = np.linspace(0, dur, n, endpoint=False)
        # Dissonant tritone
        w = (np.sin(2*np.pi*220*t) * 0.4
           + np.sin(2*np.pi*311*t) * 0.3   # Eb — tritone from A
           + np.sin(2*np.pi*440*t) * 0.15
           + np.random.uniform(-0.08, 0.08, n))  # noise
        env = np.exp(-t * 5)
        return (w * env * 32767 * 0.6).astype(np.int16)

    # ── Terminal beep ─────────────────────────────────────────────────────────
    def _build_terminal(self):
        n = int(RATE * 0.08)
        t = np.linspace(0, 0.08, n, endpoint=False)
        w = np.sin(2*np.pi*660*t) * np.exp(-t*40) * 0.5
        return (w * 32767).astype(np.int16)

    # ── Boot typing click ─────────────────────────────────────────────────────
    def _build_type_click(self):
        n = int(RATE * 0.025)
        t = np.linspace(0, 0.025, n, endpoint=False)
        w = np.random.uniform(-1, 1, n) * np.exp(-t*300) * 0.35
        return (w * 32767).astype(np.int16)

    # ── Public API ────────────────────────────────────────────────────────────
    def play(self, key):
        builders = {
            "tick":        self._build_tick,
            "select":      self._build_select,
            "scan":        self._build_scan,
            "xen":         self._build_xen,
            "terminal":    self._build_terminal,
            "boot_hum":    self._build_boot_hum,
            "transit":     self._build_transit_chime,
            "type_click":  self._build_type_click,
        }
        if key not in builders: return
        snd = self._make(key, builders[key])
        if snd:
            try: snd.play()
            except Exception: pass

    def start_drone(self):
        """Start looping CP-Violation-style ambient drone."""
        if not self.ok: return
        snd = self._make("drone", self._build_drone)
        if snd and self._drone is None:
            try:
                self._drone = pygame.mixer.Channel(0)
                self._drone.set_volume(0.45)
                self._drone.play(snd, loops=-1, fade_ms=2000)
            except Exception: pass

    def stop_drone(self, fade_ms=1500):
        if self._drone:
            try: self._drone.fadeout(fade_ms)
            except Exception: pass
            self._drone = None

    def start_transit(self):
        """Loop the transit chime quietly under everything."""
        if not self.ok: return
        snd = self._make("transit", self._build_transit_chime)
        if snd and self._transit is None:
            try:
                self._transit = pygame.mixer.Channel(1)
                self._transit.set_volume(0.28)
                self._transit.play(snd, loops=-1)
            except Exception: pass

    def stop_transit(self):
        if self._transit:
            try: self._transit.stop()
            except Exception: pass
            self._transit = None

    def play_music(self, path, loops=-1, fade_ms=3000, volume=0.7):
        """Play an MP3/OGG via pygame.mixer.music (streams, no RAM spike)."""
        if not self.ok or path is None: return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)
        except Exception as e:
            print(f"[AUDIO] music failed: {e}")

    def stop_music(self, fade_ms=1500):
        try: pygame.mixer.music.fadeout(fade_ms)
        except Exception: pass

    def music_playing(self):
        try: return pygame.mixer.music.get_busy()
        except Exception: return False

sfx = SoundEngine()

pygame.display.set_mode((W, H), OPENGL | DOUBLEBUF)
pygame.display.set_caption("HALF-LIFE 0")
clock = pygame.time.Clock()

# ── Fonts ─────────────────────────────────────────────────────────────────────
def _font(size, bold=False):
    for name in ["Courier New", "Courier", "monospace"]:
        try: return pygame.font.SysFont(name, size, bold=bold)
        except: pass
    return pygame.font.Font(None, size)

F_HUGE  = _font(96, True)
F_BIG   = _font(32, True)
F_MED   = _font(22)
F_SMALL = _font(16)
F_TINY  = _font(12)

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG     = (18,  20,  16)
C_DARK   = (28,  32,  24)
C_MID    = (55,  60,  50)
C_MUTED  = (100, 105, 90)
C_LIGHT  = (160, 165, 150)
C_WHITE  = (220, 225, 210)
C_LAMBDA = (140, 145, 130)
C_BLUE   = (80,  140, 220)
C_RED    = (200, 60,  40)
C_GREEN  = (60,  180, 80)
C_AMBER  = (200, 160, 40)
C_XEN    = (80,  200, 120)
C_PORTAL = (60,  180, 240)

def gl3(r, g, b): return (r/255.0, g/255.0, b/255.0)
def dim(c, f=0.65): return tuple(v*f for v in c)

FOG_COLOR   = (0.07, 0.08, 0.05, 1.0)
GL_FLOOR    = gl3(30,  35, 25)
GL_FLOOR2   = gl3(36,  42, 30)
GL_CEILING  = gl3(22,  26, 18)
GL_WALL     = gl3(55,  60, 45)
GL_WALL_DK  = gl3(40,  44, 32)
GL_DOOR     = gl3(40,  70, 90)
GL_TERMINAL = gl3(30,  60, 100)
GL_APT      = gl3(200, 200, 210)  # Aperture — clean white
GL_APT2     = gl3(185, 185, 195)
GL_APT_CEIL = gl3(220, 220, 230)
GL_APT_WALL = gl3(170, 170, 185)
GL_XEN      = gl3(20,  60,  45)   # Xen — dark teal organic
GL_XEN2     = gl3(15,  50,  38)
GL_XEN_CEIL = gl3(10,  35,  28)
GL_XEN_WALL = gl3(30,  80,  60)
GL_SURF     = gl3(45,  55,  35)   # Surface — grass/dirt
GL_SURF2    = gl3(38,  48,  28)
GL_SKY_CEIL = gl3(55,  80, 120)   # Surface sky ceiling

# ── Tilemap ───────────────────────────────────────────────────────────────────
T_FLOOR = 0; T_WALL = 1; T_DOOR = 2; T_VENT = 3
T_TERM  = 4; T_ITEM = 5; T_NPC  = 6
T_APT   = 7  # Aperture Science floor (white/sterile)
T_XEN   = 8  # Xen organic floor (teal/green)
T_GLASS = 9  # Glass wall / window

# ══════════════════════════════════════════════════════════════════════════════
# SAVE SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
SAVE_FILE = os.path.join(_SCRIPT_DIR, "hl0_save.json")

def save_game(data: dict):
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[SAVE] Written to {SAVE_FILE}")
        return True
    except Exception as e:
        print(f"[SAVE] Failed: {e}")
        return False

def load_game() -> dict | None:
    try:
        if not os.path.exists(SAVE_FILE): return None
        with open(SAVE_FILE) as f:
            return json.load(f)
    except Exception as e:
        print(f"[SAVE] Load failed: {e}")
        return None

def default_save():
    return {
        "level":        0,
        "health":       100,
        "suit":         100,
        "docs_found":   [],
        "missions_done":[],
        "pos":          [2.5, 1.5],
        "yaw":          90.0,
        "xen_bleed":    0.0,
    }

# ══════════════════════════════════════════════════════════════════════════════
# MISSION SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
class Mission:
    def __init__(self, mid, title, desc, steps):
        """
        steps: list of dicts with keys:
          type: "scan_doc" | "reach_tile" | "use_terminal" | "survive"
          target: doc index / (tx,tz) tile / terminal index / seconds
          hint: str
        """
        self.id    = mid
        self.title = title
        self.desc  = desc
        self.steps = steps
        self.step  = 0
        self.done  = False

    def current_hint(self):
        if self.done: return "COMPLETE"
        if self.step < len(self.steps):
            return self.steps[self.step]["hint"]
        return ""

    def check(self, event_type, value):
        if self.done: return False
        if self.step >= len(self.steps): return False
        s = self.steps[self.step]
        if s["type"] == event_type and s["target"] == value:
            self.step += 1
            if self.step >= len(self.steps):
                self.done = True
            return True
        return False

# Missions per level — list of Mission objects built fresh each load
def build_missions(level_idx):
    if level_idx == 0:
        return [
            Mission("m0_orient", "Orientation",
                "Find your bearings in Sub-Level 4.",
                [{"type":"use_terminal","target":0,
                  "hint":"Use the terminal near your starting position [E]"}]),
            Mission("m0_docs", "Project Ouroboros",
                "Recover the classified memos before they're purged.",
                [{"type":"scan_doc","target":0,
                  "hint":"Scan the first document — look for a glowing DOC marker"},
                 {"type":"scan_doc","target":1,
                  "hint":"Find the second document deeper in the facility"}]),
            Mission("m0_xen", "Anomalous Reading",
                "Trigger a dimensional bleed event and survive it.",
                [{"type":"xen_trigger","target":True,
                  "hint":"Press [F] near the vent in the west corridor"}]),
            Mission("m0_exit", "Deeper",
                "Reach the Lambda corridor exit.",
                [{"type":"reach_tile","target":(28,8),
                  "hint":"Navigate to the east passage — coordinates 28,8"}]),
        ]
    elif level_idx == 1:
        return [
            Mission("m1_power", "Lights Out",
                "Cut power to the security grid.",
                [{"type":"use_terminal","target":0,
                  "hint":"Find the power control terminal [E]"},
                 {"type":"use_terminal","target":1,
                  "hint":"Confirm shutdown at secondary terminal"}]),
            Mission("m1_docs", "Aperture Invoice",
                "Recover two more classified files.",
                [{"type":"scan_doc","target":2,
                  "hint":"Third document — Aperture Science wing"},
                 {"type":"scan_doc","target":3,
                  "hint":"Fourth document — specimen lab"}]),
            Mission("m1_vortigaunt","First Contact",
                "Reach the Vortigaunt containment cell.",
                [{"type":"reach_tile","target":(5,14),
                  "hint":"Containment is in the south-west corner"}]),
        ]
    elif level_idx == 2:
        return [
            Mission("m2_aperture","Aperture Wing",
                "Investigate the sealed Aperture Science section.",
                [{"type":"use_terminal","target":0,
                  "hint":"Hack the Aperture access terminal"},
                 {"type":"reach_tile","target":(26,4),
                  "hint":"Reach the Aperture Science lab"}]),
            Mission("m2_cascade","Point of No Return",
                "Document the dimensional cascade readings.",
                [{"type":"scan_doc","target":4,
                  "hint":"Find the cascade report in the north corridor"},
                 {"type":"use_terminal","target":2,
                  "hint":"Upload readings to the Lambda cache terminal"}]),
        ]
    elif level_idx == 3:
        return [
            Mission("m3_tram","Tram Manifest",
                "Recover the transit system manifest from the arrival terminal.",
                [{"type":"use_terminal","target":0,
                  "hint":"Use the arrival terminal — far end of the tram corridor"}]),
            Mission("m3_docs","Missing Personnel",
                "Two researchers vanished on arrival day. Find their files.",
                [{"type":"scan_doc","target":4,
                  "hint":"Personnel file — north wing"},
                 {"type":"scan_doc","target":5,
                  "hint":"Second file — south security checkpoint"}]),
            Mission("m3_exit","Into the Facility",
                "Proceed past the security checkpoint.",
                [{"type":"reach_tile","target":(58,23),
                  "hint":"Head east through the checkpoint corridor"}]),
        ]
    elif level_idx == 4:
        return [
            Mission("m4_aperture","Aperture Infiltration",
                "Hack the central Aperture Science terminal.",
                [{"type":"use_terminal","target":0,
                  "hint":"Central terminal — inner test chamber"},
                 {"type":"use_terminal","target":1,
                  "hint":"Secondary confirmation terminal"}]),
            Mission("m4_prototype","The Prototype",
                "Locate the stolen portal device documentation.",
                [{"type":"scan_doc","target":6,
                  "hint":"Portal prototype docs — inner chamber east"},
                 {"type":"scan_doc","target":7,
                  "hint":"Cave Johnson memo — south test wing"}]),
            Mission("m4_xen","Aperture Anomaly",
                "Trigger the Xen resonance in the Aperture wing.",
                [{"type":"xen_trigger","target":True,
                  "hint":"Press [F] near the test chamber power core"}]),
        ]
    elif level_idx == 5:
        return [
            Mission("m5_xen1","First Contact",
                "Survive three minutes in the Xen pocket.",
                [{"type":"xen_trigger","target":True,
                  "hint":"The border world is already destabilizing — press [F]"},
                 {"type":"use_terminal","target":0,
                  "hint":"Find the research beacon terminal"}]),
            Mission("m5_specimens","Specimen Recovery",
                "Scan the Xen biological data caches.",
                [{"type":"scan_doc","target":8,
                  "hint":"Data cache — inner ring north"},
                 {"type":"scan_doc","target":9,
                  "hint":"Data cache — inner ring south"}]),
            Mission("m5_vortigaunt","The Warning",
                "Reach the Vortigaunt communication node.",
                [{"type":"reach_tile","target":(24,14),
                  "hint":"Head to the centre of the Xen pocket"}]),
        ]
    elif level_idx == 6:
        return [
            Mission("m6_recon","Surface Recon",
                "Assess the Black Mesa perimeter for Combine activity.",
                [{"type":"use_terminal","target":0,
                  "hint":"Perimeter monitoring terminal — north fence"},
                 {"type":"use_terminal","target":1,
                  "hint":"Southern monitoring terminal"}]),
            Mission("m6_evidence","The Surveillance",
                "Find evidence of pre-incident Combine presence.",
                [{"type":"scan_doc","target":10,
                  "hint":"Buried surveillance log — east structure"},
                 {"type":"scan_doc","target":11,
                  "hint":"Satellite intercept — surface comms array"}]),
            Mission("m6_interior","Back Inside",
                "Re-enter the facility through the south access point.",
                [{"type":"reach_tile","target":(68,27),
                  "hint":"South-east corner — facility re-entry hatch"}]),
        ]
    elif level_idx == 7:
        return [
            Mission("m7_gman","He's Here",
                "Seven G-Man sightings have been reported. Document one.",
                [{"type":"reach_tile","target":(20,13),
                  "hint":"Proceed down the main corridor — he's been seen at junction 4"}]),
            Mission("m7_docs","Last Evidence",
                "Recover the final classified documents before the cascade.",
                [{"type":"scan_doc","target":12,
                  "hint":"Final memo — east alcove"},
                 {"type":"scan_doc","target":13,
                  "hint":"Lambda cache note — end of corridor"}]),
            Mission("m7_lambda","Seal the Cache",
                "Reach the Lambda cache terminal and upload everything.",
                [{"type":"use_terminal","target":0,
                  "hint":"Lambda cache terminal — end of corridor"},
                 {"type":"use_terminal","target":1,
                  "hint":"Confirm upload — secondary terminal"}]),
        ]
    return []

# ══════════════════════════════════════════════════════════════════════════════
# LEVELS  (T=terminal, I=item/doc, N=npc, D=door, V=vent, E=exit)
# ══════════════════════════════════════════════════════════════════════════════
LEVELS = [
    # ── Level 0: Sub-Level 4 Entry ───────────────────────────────────────────
    [
        "##############################",
        "#............................#",
        "#....T.......................#",
        "#............................#",
        "###.######.########.######.##",
        "#..D......D.......D.......D.#",
        "#....................T.......#",
        "#..N.................N.......#",
        "######.##########.###########",
        "#.V..........................#",
        "#.....T.....T.....T..........#",
        "#.....N......N...............#",
        "######.######.#######.#######",
        "#............I...............#",
        "#............................#",
        "#....N.....I.................#",
        "#............................#",
        "###########################E#",
    ],
    # ── Level 1: Anomalous Materials Lab ─────────────────────────────────────
    [
        "##########E###################",
        "#...........................V#",
        "#.N..T......................N.#",
        "#............................#",
        "#.####.##########.####.######",
        "#.#..............#..........#",
        "#.#....I.........#....T.....#",
        "#.D....N.........D..........#",
        "#.#..............#..........#",
        "#.####.##########.###########",
        "#............................#",
        "#....T......T.......T........#",
        "##########.##################",
        "#............................#",
        "#.V..N.......N...............#",
        "#..............I.............#",
        "#............................#",
        "###########################E#",
    ],
    # ── Level 2: Lambda Complex / Aperture Wing ───────────────────────────────
    [
        "##############################",
        "#............................#",
        "#....T.......................#",
        "#............................#",
        "######.####.E.####.###########",
        "#..........#...#............#",
        "#..N.......#...#.....T......#",
        "#..........#...#............#",
        "######.####.###.####.########",
        "#............................#",
        "#.....I......T......I........#",
        "#.....N......N...............#",
        "######.######.#######.#######",
        "#............I...............#",
        "#.V..........................#",
        "#....N.......................#",
        "#............................#",
        "##############################",
    ],

    # ── Level 3: Tram Arrival ────────────────────────────────────────────────
    # 60 wide x 24 tall  |  You arrive at Black Mesa on the tram
    [
        "############################################################",
        "#.T........................................................#",
        "#..........................................................#",
        "#..N.......................................................#",
        "#####.######.########.########.########.########.##########",
        "#..........D..........D.........D........D.................#",
        "#..N.......D..........D.........D........D.....T..N.......#",
        "#..........D..........D.........D........D.................#",
        "#####.######.########.########.########.########.##########",
        "#..........................................................#",
        "#....I..................N..............N....................#",
        "#..........T.......................................T.......#",
        "######.########.########.########.########.################",
        "#.V........................................................#",
        "#..........................................................#",
        "#....N.............N.................N.....................#",
        "#..........................................................#",
        "######.########.########.########.########.################",
        "#....I.....................................................#",
        "#..........................................................#",
        "#..N.......T..............T................T...............#",
        "#..........................................................#",
        "#.......................................................E..#",
        "############################################################",
    ],
    # ── Level 4: Aperture Science Wing ──────────────────────────────────────
    # 55 wide x 30 tall  |  Sterile white test chambers, A=Aperture floor
    [
        "#######################################################",
        "#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#",
        "#A.T.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.T.AAAAA#",
        "#AAAAAA.####################################.AAAAAAA#",
        "#AAAAAA.#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#.AAAAAAA#",
        "#AAAAAA.#AA.T.AAAAAAAAAAAAAAAAAAAAAA.T.AAA#.AAAAAAA#",
        "#AAAAAA.#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#.AAAAAAA#",
        "#AAAAAA.#AA.N.AAAAAAAAAAAAAAAAAAAAAA.N.AAA#.AAAAAAA#",
        "#AAAAAA.#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#.AAAAAAA#",
        "#AAAAAA.#AA.I.AAAAAAAAAAAAA.I.AAAAAAAAAAAA#.AAAAAAA#",
        "#AAAAAA.#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#.AAAAAAA#",
        "#AAAAAA.####################################.AAAAAAA#",
        "#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#",
        "#AAAAAA######.##########.##########.######AAAAAAAAA#",
        "#AAAAAA#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#AAAAAAAAA#",
        "#AAAAAA#AA.N.AAAAAAAAAAAAAAAAAAAAAA.N.AAA#AAAAAAAAA#",
        "#AAAAAA#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#AAAAAAAAA#",
        "#AAAAAA#AA.T.AAAAAA.I.AAAAAAA.I.AAAA.T.AA#AAAAAAAAA#",
        "#AAAAAA#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#AAAAAAAAA#",
        "#AAAAAA#AA.N.AAAAAAAAAAAAAAAAAAAAAA.N.AAA#AAAAAAAAA#",
        "#AAAAAA#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#AAAAAAAAA#",
        "#AAAAAA######.##########.##########.######AAAAAAAAA#",
        "#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#",
        "#AA.T.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.T.AAAAA#",
        "#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#",
        "#AA.N.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.N.AAAAA#",
        "#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#",
        "#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#",
        "#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA#",
        "########################################################E",
    ],
    # ── Level 5: Xen Borderworld Pocket ─────────────────────────────────────
    # 50 wide x 30 tall  |  Organic alien geometry, X=Xen floor
    [
        "##################################################",
        "#XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX#",
        "#XX.....XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX.....XX#",
        "#XX.....XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX.....XX#",
        "#XX.T...XXXXXXXXXXXXXXXX.XXXXXXXXXXXXXXXXX.T..XX#",
        "#XXXXXXXXXXXXXXXXXXXXXXX.XXXXXXXXXXXXXXXXXXXXXXXX#",
        "#XXXXXXX.###############.###############.XXXXXXXX#",
        "#XXXXXXX.#XXXXXXXXXXXXXXXXXXXXXXXXXXXXX#.XXXXXXXX#",
        "#XXXXXXX.#XXX.N.XXXXXXXXXXXXXXX.N.XXXX#.XXXXXXXX#",
        "#XXXXXXX.#XXXXXXXXXXXXXXXXXXXXXXXXXXXXX#.XXXXXXXX#",
        "#XXXXXXX.#XXX...XXXXXXXXXXXXXXX...XXXX#.XXXXXXXX#",
        "#XXXXXXX.#XXXXXXXXXXXXXXXXXXXXXXXXXXXXX#.XXXXXXXX#",
        "#XXXXXXX.#XXX.I.XXXXXXXXXXXXXXX.I.XXXX#.XXXXXXXX#",
        "#XXXXXXX.#XXXXXXXXXXXXXXXXXXXXXXXXXXXXX#.XXXXXXXX#",
        "#XXXXXXX.###.################.###.#####.XXXXXXXX#",
        "#XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX#",
        "#XX.N...XXXXXXXXXXXX.T.XXXXXXXXXXXXXXXXX...N.XX#",
        "#XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX#",
        "#XXXXXXX.##########.XXXXXX.##########.XXXXXXXXXX#",
        "#XXXXXXX.#XXXXXXXXXXXXXXXXXXXXXXXXXX#.XXXXXXXXXX#",
        "#XXXXXXX.#XX.N.XXXXXXXXXXXX.N.XXXXX#.XXXXXXXXXX#",
        "#XXXXXXX.#XXXXXXXXXXXXXXXXXXXXXXXXXX#.XXXXXXXXXX#",
        "#XXXXXXX.#XX.I.XXXX.T.XXXXX.I.XXXXX#.XXXXXXXXXX#",
        "#XXXXXXX.#XXXXXXXXXXXXXXXXXXXXXXXXXX#.XXXXXXXXXX#",
        "#XXXXXXX.##########.XXXXXX.##########.XXXXXXXXXX#",
        "#XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX#",
        "#XX.....XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX.....XX#",
        "#XX.T...XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX.T....XX#",
        "#XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX#",
        "#################################################E",
    ],
    # ── Level 6: Black Mesa Surface / Exterior ───────────────────────────────
    # 70 wide x 28 tall  |  Wide open, S=surface floor, buildings at edges
    [
        "######################################################################",
        "#......................................................................#",
        "#....T.............................................................T....#",
        "#......................................................................#",
        "#......N.....................................................N..........#",
        "#......................................................................#",
        "#####.########.########.########.########.########.########.############",
        "#......................................................................#",
        "#......................................................................#",
        "#....N...................T.......................T.................N.....#",
        "#......................................................................#",
        "#......................................................................#",
        "#....I.........################################################.I.....#",
        "#...............#..............................................#..........#",
        "#...............#....N..................................N.....#..........#",
        "#...............#..............................................#..........#",
        "#...............#....T..................................T.....#..........#",
        "#...............#..............................................#..........#",
        "#...............################################################..........#",
        "#......................................................................#",
        "#......N.....................................................N..........#",
        "#......................................................................#",
        "#####.########.########.########.########.########.########.############",
        "#......................................................................#",
        "#....T..................................................I..............#",
        "#......................................................................#",
        "#......N.....................................................N..........#",
        "#####################################################################E##",
    ],
    # ── Level 7: G-Man Corridor ─────────────────────────────────────────────
    # 42 wide x 28 tall  |  Narrow, scripted, eerie — G-Man sighting here
    [
        "##########################################",
        "#........................................#",
        "#.T......................................#",
        "#........................................#",
        "####.####.####.####.####.####.####.######",
        "#........................................#",
        "#....N...................................#",
        "#........................................#",
        "##########.####.####.####.####.##########",
        "#........................................#",
        "#........................................#",
        "#....T.....I.........T...................#",
        "#........................................#",
        "####.####.####G####.####.####.############",
        "#........................................#",
        "#....N...................................#",
        "#........................................#",
        "##########.####.####.####.####.##########",
        "#........................................#",
        "#....T...................................#",
        "#........I...............................#",
        "#....N...................................#",
        "####.####.####.####.####.####.####.######",
        "#........................................#",
        "#........................................#",
        "#....T...................................#",
        "#........................................#",
        "#########################################E",
    ],
]

LEVEL_NAMES = [
    "SUB-LEVEL 4  //  SECTOR C",
    "ANOMALOUS MATERIALS LAB",
    "LAMBDA COMPLEX  //  APERTURE WING",
    "TRAM ARRIVAL  //  BLACK MESA TRANSIT",
    "APERTURE SCIENCE WING  //  SECTOR F",
    "XEN BORDERWORLD  //  POCKET DIMENSION",
    "BLACK MESA SURFACE  //  NEW MEXICO",
    "LAMBDA CORRIDOR  //  G-MAN SIGHTING",
]

LEVEL_SPAWNS = [
    (2.5, 1.5, 90.0),   # 0 Sub-Level 4
    (2.5, 16.5, 0.0),   # 1 Anomalous Materials
    (2.5, 1.5, 90.0),   # 2 Lambda Complex
    (2.5, 1.5, 90.0),   # 3 Tram Arrival
    (2.5, 1.5, 90.0),   # 4 Aperture Wing
    (2.5, 1.5, 90.0),   # 5 Xen Pocket
    (2.5, 1.5, 90.0),   # 6 Surface
    (2.5, 1.5, 90.0),   # 7 G-Man Corridor
]

_CHARS = {'#':T_WALL,'.':T_FLOOR,'D':T_DOOR,'V':T_VENT,'T':T_TERM,
          'I':T_ITEM,'N':T_NPC,'E':T_FLOOR,
          'A':T_APT,  # Aperture floor
          'X':T_XEN,  # Xen floor
          'G':T_GLASS,'S':T_FLOOR,  # S=surface open floor
          }

def parse_level(idx):
    rows = LEVELS[idx]
    return [[_CHARS.get(c, T_FLOOR) for c in row] for row in rows]

def find_exits(idx):
    exits = []
    for ry, row in enumerate(LEVELS[idx]):
        for rx, c in enumerate(row):
            if c == 'E':
                exits.append((rx, ry))
    return exits


# ══════════════════════════════════════════════════════════════════════════════
# CONTROLLER
# 8BitDo Pro 2: analog stick + D-pad, X-Input or D-Input
# 8BitDo Zero 2: D-pad only, no sticks
# Any other SDL gamepad: treated as Pro 2 profile
# ══════════════════════════════════════════════════════════════════════════════
class Controller:
    DEAD = 0.15  # dead zone for analog sticks

    def __init__(self):
        pygame.joystick.init()
        self.joy     = None
        self.profile = "none"   # "zero2" | "pro2" | "generic"
        self.name    = "none"
        self.move    = 0.0      # forward/back  (-1 to 1)
        self.turn    = 0.0      # left/right    (-1 to 1)
        self.action  = False    # A / face south
        self.cancel  = False    # B / face east
        self.start   = False
        self._detect()

    def _detect(self):
        for i in range(pygame.joystick.get_count()):
            j = pygame.joystick.Joystick(i); j.init()
            n = j.get_name().lower()
            if "zero 2" in n or "zero2" in n:
                self.profile = "zero2"
            elif "8bitdo" in n or "pro 2" in n or "pro2" in n:
                self.profile = "pro2"
            else:
                self.profile = "generic"
            self.joy  = j
            self.name = j.get_name()
            return

    def update(self):
        if not self.joy:
            self.move = self.turn = 0.0
            self.action = self.cancel = self.start = False
            return
        try:
            nb = self.joy.get_numbuttons()

            if self.profile == "zero2":
                # ── Zero 2: no analog sticks, use D-pad hat ──
                hat = self.joy.get_hat(0) if self.joy.get_numhats() > 0 else (0, 0)
                self.move  =  float(hat[1])   # hat north = +1 = forward
                self.turn  = -float(hat[0])   # hat east  = +1 = turn right (negative)
                # Zero 2 button layout (Switch mode):  B=0 A=1 Y=2 X=3 L=4 R=5 Start=8
                self.action = bool(self.joy.get_button(1)) if nb > 1 else False
                self.cancel = bool(self.joy.get_button(0)) if nb > 0 else False
                self.start  = bool(self.joy.get_button(8)) if nb > 8 else False

            else:
                # ── Pro 2 / generic: left analog stick primary, D-pad override ──
                axes = self.joy.get_numaxes()
                if axes >= 2:
                    raw_y = self.joy.get_axis(1)  # up = -1
                    raw_x = self.joy.get_axis(0)  # right = +1
                    self.move = (-raw_y) if abs(raw_y) > self.DEAD else 0.0
                    self.turn = ( raw_x) if abs(raw_x) > self.DEAD else 0.0

                # D-pad hat overrides stick when pressed
                if self.joy.get_numhats() > 0:
                    hat = self.joy.get_hat(0)
                    if hat[0] or hat[1]:
                        self.move =  float(hat[1])
                        self.turn = -float(hat[0])

                # Pro 2 X-Input: A=0 B=1 X=2 Y=3 LB=4 RB=5 Back=6 Start=7
                self.action = bool(self.joy.get_button(0)) if nb > 0 else False
                self.cancel = bool(self.joy.get_button(1)) if nb > 1 else False
                self.start  = bool(self.joy.get_button(7)) if nb > 7 else False

        except Exception:
            self.move = self.turn = 0.0

    def hat_event(self, event):
        """Call from JOYHATMOTION to get discrete nav events (-1, 0, 1)."""
        if event.type == JOYHATMOTION:
            return event.value  # (x, y)
        return (0, 0)

    @property
    def connected(self): return self.joy is not None

    def status_str(self):
        if not self.connected: return "No controller"
        return f"{self.name}  [{self.profile.upper()}]"


ctrl = Controller()


# ══════════════════════════════════════════════════════════════════════════════
# CAMERA  — tank controls, no pitch
# ══════════════════════════════════════════════════════════════════════════════
class Camera:
    SPEED  = 4.5    # units / sec
    TSENS  = 120.0  # degrees / sec

    def __init__(self, x, z, yaw=90.0, height=0.55):
        self.x, self.z = float(x), float(z)
        self.y   = height
        self.yaw = yaw  # 0° = looking -Z; 90° = looking +X

    def fwd(self):
        r = math.radians(self.yaw)
        return math.sin(r), -math.cos(r)

    MSENS  = 0.15   # mouse sensitivity degrees per pixel

    def update(self, dt, keys, tilemap):
        # Forward / back — W/S or arrow up/down
        m = 0.0
        if keys[K_w] or keys[K_UP]:    m =  1.0
        if keys[K_s] or keys[K_DOWN]:  m = -1.0

        # Turn — arrow keys or mouse X
        t = 0.0
        if keys[K_LEFT]:  t = -1.0
        if keys[K_RIGHT]: t =  1.0

        # Mouse look — only when mouse is captured
        if pygame.event.get_grab():
            mx, _ = pygame.mouse.get_rel()
            self.yaw += mx * self.MSENS
        else:
            self.yaw += t * self.TSENS * dt

        # Strafe — A/D
        st = 0.0
        if keys[K_a]: st =  1.0
        if keys[K_d]: st = -1.0

        # Controller blends in
        if abs(ctrl.move) > abs(m):  m  = ctrl.move
        if abs(ctrl.turn) > abs(t):  t  = ctrl.turn

        if not pygame.event.get_grab():
            self.yaw += t * self.TSENS * dt

        fx, fz = self.fwd()
        # Strafe direction is perpendicular to forward
        sx, sz = fz, -fx   # rotate fwd 90 degrees

        nx = self.x + fx * m * self.SPEED * dt + sx * st * self.SPEED * dt
        nz = self.z + fz * m * self.SPEED * dt + sz * st * self.SPEED * dt

        if not self._solid(nx, self.z, tilemap): self.x = nx
        if not self._solid(self.x, nz, tilemap): self.z = nz

    def _solid(self, x, z, tilemap, r=0.28):
        for dx, dz in ((r,r),(-r,r),(r,-r),(-r,-r)):
            tx, tz = int(x+dx), int(z+dz)
            if 0 <= tz < len(tilemap) and 0 <= tx < len(tilemap[0]):
                if tilemap[tz][tx] == T_WALL: return True
            else: return True
        return False

    def apply(self):
        glRotatef(self.yaw, 0, 1, 0)
        glTranslatef(-self.x, -self.y, -self.z)


# ══════════════════════════════════════════════════════════════════════════════
# GL UTILITIES
# ══════════════════════════════════════════════════════════════════════════════
def init_gl():
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LEQUAL)
    glShadeModel(GL_FLAT)
    glEnable(GL_FOG)
    glFogi(GL_FOG_MODE, GL_LINEAR)
    glFogfv(GL_FOG_COLOR, FOG_COLOR)
    glFogf(GL_FOG_START, 6.0)
    glFogf(GL_FOG_END,  24.0)
    glClearColor(*FOG_COLOR)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(FOV, W/H, NEAR, FAR)
    glMatrixMode(GL_MODELVIEW)


def draw_overlay(surf):
    """Blit a pygame RGBA surface as a fullscreen 2D overlay (no depth)."""
    data = pygame.image.tostring(surf, "RGBA", True)
    tex  = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, W, H, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    glOrtho(0, W, 0, H, -1, 1)
    glMatrixMode(GL_MODELVIEW);  glPushMatrix(); glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(1,1,1,1)
    glBegin(GL_QUADS)
    glTexCoord2f(0,0); glVertex2f(0,0)
    glTexCoord2f(1,0); glVertex2f(W,0)
    glTexCoord2f(1,1); glVertex2f(W,H)
    glTexCoord2f(0,1); glVertex2f(0,H)
    glEnd()
    glDisable(GL_BLEND); glDisable(GL_TEXTURE_2D)
    glDeleteTextures([tex])
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW);  glPopMatrix()


def txt2d(surf, text, font, color, x, y, anchor="topleft"):
    s = font.render(text, True, color[:3])
    r = s.get_rect(**{anchor: (x, y)})
    surf.blit(s, r)
    return r

def lerp_c(a, b, t):
    return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL GEOMETRY
# ══════════════════════════════════════════════════════════════════════════════
def draw_level(tilemap):
    rows = len(tilemap)
    cols = max(len(r) for r in tilemap)
    glBegin(GL_QUADS)
    # Detect map theme from tile majority
    flat = [t for row in tilemap for t in row]
    _apt  = flat.count(T_APT)  > len(flat)*0.05
    _xen  = flat.count(T_XEN)  > len(flat)*0.05
    _surf = not _apt and not _xen and flat.count(T_FLOOR) > flat.count(T_WALL)*3
    # Wall colours per theme
    wA  = GL_APT_WALL if _apt else (GL_XEN_WALL if _xen else GL_WALL)
    wDk = tuple(v*0.7 for v in wA)

    for ry in range(rows):
        row = tilemap[ry]
        for rx in range(len(row)):
            tile = row[rx]
            x, z = float(rx), float(ry)

            def nb(ddx, ddz):
                ny2, nx2 = ry+ddz, rx+ddx
                if 0<=ny2<rows and 0<=nx2<len(tilemap[ny2]):
                    return tilemap[ny2][nx2]
                return T_WALL

            if tile != T_WALL:
                # Floor
                # Floor colour by tile type
                if tile == T_APT:      fc = GL_APT2 if (rx+ry)%2 else GL_APT
                elif tile == T_XEN:    fc = GL_XEN2 if (rx+ry)%2 else GL_XEN
                elif tile == T_DOOR:   fc = gl3(35,60,80)
                elif tile == T_TERM:   fc = gl3(25,50,85)
                elif tile == T_ITEM:   fc = gl3(50,70,35)
                else:                  fc = GL_SURF2 if _surf else (GL_FLOOR2 if (rx+ry)%2 else GL_FLOOR)
                glColor3f(*fc)
                glVertex3f(x,   0, z+1); glVertex3f(x+1, 0, z+1)
                glVertex3f(x+1, 0, z  ); glVertex3f(x,   0, z  )
                # Ceiling — varies by theme
                if _apt:   cc = GL_APT_CEIL
                elif _xen: cc = GL_XEN_CEIL
                elif _surf:cc = GL_SKY_CEIL
                else:      cc = GL_CEILING
                glColor3f(*cc)
                glVertex3f(x,   1, z  ); glVertex3f(x+1, 1, z  )
                glVertex3f(x+1, 1, z+1); glVertex3f(x,   1, z+1)
            else:
                # Only draw wall faces bordering open space (back-face cull manually)
                # South (z+1)
                if nb(0,1) != T_WALL:
                    glColor3f(*wA)
                    glVertex3f(x+1,0,z+1); glVertex3f(x,  0,z+1)
                    glVertex3f(x,  1,z+1); glVertex3f(x+1,1,z+1)
                # North (z-1)
                if nb(0,-1) != T_WALL:
                    glColor3f(*wDk)
                    glVertex3f(x,  0,z  ); glVertex3f(x+1,0,z  )
                    glVertex3f(x+1,1,z  ); glVertex3f(x,  1,z  )
                # East (x+1)
                if nb(1,0) != T_WALL:
                    glColor3f(*wA)
                    glVertex3f(x+1,0,z  ); glVertex3f(x+1,0,z+1)
                    glVertex3f(x+1,1,z+1); glVertex3f(x+1,1,z  )
                # West (x-1)
                if nb(-1,0) != T_WALL:
                    glColor3f(*wDk)
                    glVertex3f(x,  0,z+1); glVertex3f(x,  0,z  )
                    glVertex3f(x,  1,z  ); glVertex3f(x,  1,z+1)
                # Top cap (player can't see from above, but useful for sandbox view)
                glColor3f(*dim(GL_WALL_DK, 0.7))
                glVertex3f(x,  1,z  ); glVertex3f(x+1,1,z  )
                glVertex3f(x+1,1,z+1); glVertex3f(x,  1,z+1)
    glEnd()


def draw_billboard(cx, cz, col_rgb, cam_x, cam_z, scale=0.35):
    """NPC/entity billboard — always faces camera, centered at floor level."""
    dx = cam_x - cx; dz = cam_z - cz
    dist = math.hypot(dx, dz)
    if dist < 0.01: return
    pw = (dz/dist)*scale; ph = -(dx/dist)*scale
    h0, h1 = 0.05, 0.9
    glBegin(GL_QUADS)
    glColor3f(*[v/255.0 for v in col_rgb])
    glVertex3f(cx-pw, h0, cz-ph); glVertex3f(cx+pw, h0, cz+ph)
    glVertex3f(cx+pw, h1, cz+ph); glVertex3f(cx-pw, h1, cz-ph)
    glEnd()


# ══════════════════════════════════════════════════════════════════════════════
# G-MAN SCRIPTED ENCOUNTER
# Appears at predetermined positions on Level 7.
# Stands motionless. Vanishes when player gets within 3 units.
# ══════════════════════════════════════════════════════════════════════════════
GMAN_POSITIONS = [
    (20.5, 13.5),  # junction 4 — main corridor
    (10.5,  6.5),  # north alcove
    (30.5, 19.5),  # south passage
]

class GManEncounter:
    VANISH_DIST  = 3.0
    FADE_SPEED   = 2.5

    def __init__(self):
        self.sightings = [
            {"x": x, "z": z, "alpha": 1.0, "gone": False}
            for x, z in GMAN_POSITIONS
        ]
        self.total_seen = 0

    def update(self, dt, cam_x, cam_z):
        for s in self.sightings:
            if s["gone"]: continue
            dist = math.hypot(cam_x - s["x"], cam_z - s["z"])
            if dist < self.VANISH_DIST:
                s["alpha"] -= dt * self.FADE_SPEED
                if s["alpha"] <= 0:
                    s["alpha"] = 0.0
                    s["gone"]  = True
                    self.total_seen += 1
                    notifier.push(
                        f"[G-MAN]  Sighting {self.total_seen}/{len(self.sightings)} — he was just here.",
                        (140, 145, 130), t=5.0)

    def draw(self, cam_x, cam_z):
        for s in self.sightings:
            if s["gone"]: return
            a = s["alpha"]
            if a <= 0: continue
            # Tall, thin, dark grey — suit silhouette
            cx, cz = s["x"], s["z"]
            dx = cam_x - cx; dz = cam_z - cz
            dist = math.hypot(dx, dz)
            if dist < 0.01: continue
            pw = (dz/dist) * 0.18; ph = -(dx/dist) * 0.18
            glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glBegin(GL_QUADS)
            # Body — dark suit
            glColor4f(0.15, 0.15, 0.18, a)
            glVertex3f(cx-pw, 0.0, cz-ph); glVertex3f(cx+pw, 0.0, cz+ph)
            glVertex3f(cx+pw, 0.85, cz+ph); glVertex3f(cx-pw, 0.85, cz-ph)
            glEnd()
            # Head
            glBegin(GL_QUADS)
            glColor4f(0.72, 0.65, 0.55, a)
            glVertex3f(cx-pw*0.6, 0.85, cz-ph*0.6)
            glVertex3f(cx+pw*0.6, 0.85, cz+ph*0.6)
            glVertex3f(cx+pw*0.6, 1.05, cz+ph*0.6)
            glVertex3f(cx-pw*0.6, 1.05, cz-ph*0.6)
            glEnd()
            # Briefcase
            glBegin(GL_QUADS)
            glColor4f(0.22, 0.22, 0.25, a)
            glVertex3f(cx+pw*0.8, 0.12, cz+ph*0.8)
            glVertex3f(cx+pw*1.5, 0.12, cz+ph*1.5)
            glVertex3f(cx+pw*1.5, 0.42, cz+ph*1.5)
            glVertex3f(cx+pw*0.8, 0.42, cz+ph*0.8)
            glEnd()
            glDisable(GL_BLEND)


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFIER
# ══════════════════════════════════════════════════════════════════════════════
class Notifier:
    def __init__(self):
        self.q = []
    def push(self, msg, color=C_WHITE, t=3.5):
        self.q.append([msg, color, t])
    def update(self, dt):
        for i in self.q: i[2] -= dt
        self.q = [i for i in self.q if i[2] > 0]
    def draw(self, surf):
        y = H - 32
        for msg, col, timer in reversed(self.q[-5:]):
            a = int(min(1.0, timer*2)*255)
            s = F_SMALL.render(msg, True, col[:3]); s.set_alpha(a)
            surf.blit(s, (14, y-s.get_height())); y -= s.get_height()+2

    def draw_gl(self):
        """Draw notifications as a standalone GL overlay (no external surf needed)."""
        if not self.q: return
        surf = pygame.Surface((W, H), pygame.SRCALPHA)
        self.draw(surf)
        draw_overlay(surf)

notifier = Notifier()


# ══════════════════════════════════════════════════════════════════════════════
# BOOT SEQUENCE STATE
# Mirrors the concept video: black → λ fades in → HALF LIFE 0 types in →
# transit chime + ambient drone → Black Mesa transit text scrolls →
# fades to menu
# ══════════════════════════════════════════════════════════════════════════════
TRANSIT_LINES = [
    "Welcome to the Black Mesa Transit System.",
    "This automated train is provided for the",
    "convenience of the Black Mesa Research Facility.",
    "Please keep your limbs inside the train",
    "at all times.",
    "",
    "Black Mesa Research Facility assumes no",
    "responsibility for injuries sustained",
    "during transit.",
    "",
    "Prepare for departure.",
]

class BootState:
    """
    Boot sequence matching the concept video:
    Black → VALVE logo → TCF logo → HL0 title → LOADING → menu
    Music: 01_Hazardous_Environments.mp3 starts during HL0 title
    """
    # All times snapped to 24fps frame boundaries (frame / 24)
    T_VALVE_IN   = 68/24   # frame 68
    T_VALVE_HOLD = 83/24   # frame 83  (fully opaque)
    T_VALVE_OUT  = 292/24  # frame 292
    T_TCF_IN     = 385/24  # frame 385 (blank gap 292→385)
    T_TCF_HOLD   = 404/24  # frame 404 (fully opaque)
    T_TCF_OUT    = 602/24  # frame 602
    T_HL0_IN     = 620/24  # frame 620 — after TCF fades
    T_MUSIC_IN   = 0.0     # start immediately
    T_HL0_OUT    = 700/24  # frame 700
    T_LOAD_IN    = 710/24  # frame 710
    T_LOAD_OUT   = 780/24  # frame 780
    T_DONE       = 800/24  # frame 800
    FADE_DUR     = 15/24   # 15-frame crossfade
    SKIP_HOLD    = 0.35

    def __init__(self):
        self.t       = 0.0
        self.skip_t  = 0.0
        self._music_started = False
        self._tex    = {}
        self._loaded = False

    def _load_textures(self):
        if self._loaded: return
        self._loaded = True
        for key, fname in [
            ("valve",   "logo_valve.png"),
            ("tcf",     "logo_tcf.png"),
            ("hl0",     "logo_hl0.png"),
            ("loading", "logo_loading.png"),
            ("bg",      "AutomationBuilding.png"),
        ]:
            p = asset(fname)
            r = load_gl_texture(p)
            self._tex[key] = r
            print(f"[ASSET] {fname} → {'ok' if r else 'MISSING'}")

    def _alpha_for(self, t, t_in, t_hold, t_out, fade_out_frames=20):
        """0→1 from t_in→t_hold, held at 1 until fade starts, then 1→0."""
        if t < t_in or t > t_out: return 0.0
        fade_out = fade_out_frames / 24.0
        if t < t_hold: return (t - t_in) / max(0.001, t_hold - t_in)
        if t > t_out - fade_out: return max(0.0, (t_out - t) / fade_out)
        return 1.0

    def handle(self, event):
        if event.type == KEYDOWN and event.key in (K_RETURN, K_SPACE, K_ESCAPE):
            self.skip_t += 0.02
        if event.type == JOYBUTTONDOWN:
            self.skip_t += 0.02

    def update(self, dt):
        self.t += dt
        keys = pygame.key.get_pressed()
        if any([keys[K_RETURN], keys[K_SPACE], keys[K_ESCAPE]]):
            self.skip_t += dt
            if self.skip_t >= self.SKIP_HOLD:
                sfx.stop_drone(200)
                return "menu"
        else:
            self.skip_t = 0.0

        if self.t >= self.T_MUSIC_IN and not self._music_started:
            self._music_started = True
            sfx.play_music(asset("01_Hazardous_Environments.mp3"),
                           loops=-1, fade_ms=800, volume=0.65)

        # Fade music out as loading screen comes in
        if self.t >= self.T_LOAD_IN:
            fade_vol = max(0.0, 1.0 - (self.t - self.T_LOAD_IN) / 1.8)
            try: pygame.mixer.music.set_volume(0.65 * fade_vol)
            except Exception: pass

        if self.t >= self.T_DONE:
            return "menu"

    def draw(self):
        self._load_textures()
        glClearColor(0, 0, 0, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # VALVE logo — 68→83 fade in (15f), static 83→272, 272→292 fade out (20f)
        a = self._alpha_for(self.t, self.T_VALVE_IN, self.T_VALVE_HOLD,
                            self.T_VALVE_OUT, fade_out_frames=20)
        if a > 0:
            draw_centered_tex(self._tex.get("valve"), W//2, H//2, scale=0.7, alpha=a)

        # TCF logo — 385→404 fade in (19f), static 404→532, 532→602 fade out (70f)
        a = self._alpha_for(self.t, self.T_TCF_IN, self.T_TCF_HOLD,
                            self.T_TCF_OUT, fade_out_frames=70)
        if a > 0:
            draw_centered_tex(self._tex.get("tcf"), W//2, H//2, scale=0.7, alpha=a)

        # HL0 title — kept timing, simple fade
        if self.T_HL0_IN <= self.t <= self.T_HL0_OUT:
            fade = self.FADE_DUR
            if self.t < self.T_HL0_IN + fade:
                a = (self.t - self.T_HL0_IN) / fade
            elif self.t > self.T_HL0_OUT - fade:
                a = (self.T_HL0_OUT - self.t) / fade
            else:
                a = 1.0
            draw_centered_tex(self._tex.get("hl0"), W//2, H//2, scale=0.85, alpha=a)

        # LOADING screen — bottom-left corner, 15f fade in, 15f fade out
        t_load_hold = self.T_LOAD_IN + 15/24
        a = self._alpha_for(self.t, self.T_LOAD_IN, t_load_hold, self.T_LOAD_OUT, fade_out_frames=15)
        if a > 0 and self._tex.get("loading"):
            _, lw, lh = self._tex["loading"]
            scale = 0.7
            pad   = 32
            draw_centered_tex(self._tex.get("loading"),
                              int(lw * scale / 2) + pad,
                              H - int(lh * scale / 2) - pad,
                              scale=scale, alpha=a)

        # Fade to black at very end → menu
        if self.t >= self.T_LOAD_OUT:
            fade_a = min(1.0, (self.t - self.T_LOAD_OUT) / (self.T_DONE - self.T_LOAD_OUT))
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            surf.fill((0, 0, 0, int(fade_a * 255)))
            draw_overlay(surf)

        # Skip hint
        if self.t > 1.0:
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            a2   = int(min(1.0, (self.t-1.0)/1.0) * 70)
            s    = F_TINY.render("HOLD  ENTER  TO  SKIP", True, C_MID[:3])
            s.set_alpha(a2)
            surf.blit(s, (W//2 - s.get_width()//2, H - 28))
            draw_overlay(surf)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU STATE
# ══════════════════════════════════════════════════════════════════════════════
class MenuState:
    SUBS = {
        "CONTINUE":      "Resume from last save.",
        "NEW GAME":      "Start from the beginning. Overwrites save.",
        "PLAY":          "Begin the anomaly. Black Mesa — Sub-Level 4.",
        "SANDBOX":       "3D freeplay. Spawn entities. Physics.",
        "-BLUE SHIFT-":  "Barney Calhoun campaign. [Requires main campaign]",
        "AWARDS":        "Track discoveries and achievements.",
        "OPTIONS":       "Audio, video, controls.",
        "MODEL VIEWER":  "Inspect every entity.",
        "QUIT":          "Exit.",
    }

    def __init__(self):
        self.sel    = 0
        self.t      = 0.0
        self._bg    = None
        self._prev_sel = -1
        # Build item list based on whether a save exists
        save = load_game()
        if save:
            lvl  = save.get("level", 0)
            name = LEVEL_NAMES[min(lvl, len(LEVEL_NAMES)-1)]
            self.ITEMS = [
                (f"CONTINUE",        "campaign_continue"),
                ("NEW GAME",          "campaign_new"),
                ("SANDBOX",           "sandbox"),
                ("AWARDS",            None),
                ("-BLUE SHIFT-",      None),
                ("OPTIONS",           None),
                ("MODEL VIEWER",      None),
                ("QUIT",              "quit"),
            ]
            self.SUBS["CONTINUE"] = f"Resume: {name}"
        else:
            self.ITEMS = [
                ("PLAY",              "campaign"),
                ("SANDBOX",           "sandbox"),
                ("AWARDS",            None),
                ("-BLUE SHIFT-",      None),
                ("OPTIONS",           None),
                ("MODEL VIEWER",      None),
                ("QUIT",              "quit"),
            ]

    def handle(self, event):
        if event.type == KEYDOWN:
            if event.key == K_UP:
                self.sel = (self.sel-1) % len(self.ITEMS); sfx.play("tick")
            if event.key == K_DOWN:
                self.sel = (self.sel+1) % len(self.ITEMS); sfx.play("tick")
            if event.key in (K_RETURN, K_SPACE):
                sfx.play("select")
                result = self.ITEMS[self.sel][1]
                if result == "campaign_new":
                    if os.path.exists(SAVE_FILE):
                        os.remove(SAVE_FILE)
                    return "campaign"
                return result
            if event.key == K_ESCAPE: return "quit"
        if event.type == JOYHATMOTION:
            v = event.value
            if v[1] == 1:  self.sel = (self.sel-1) % len(self.ITEMS); sfx.play("tick")
            if v[1] == -1: self.sel = (self.sel+1) % len(self.ITEMS); sfx.play("tick")
        if event.type == JOYBUTTONDOWN:
            if ctrl.profile == "zero2":
                if event.button == 1: sfx.play("select"); return self.ITEMS[self.sel][1]
            else:
                if event.button == 0:
                    sfx.play("select")
                    result = self.ITEMS[self.sel][1]
                    if result == "campaign_new":
                        if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
                        return "campaign"
                    return result
                if event.button == 7: return "quit"

    def update(self, dt):
        self.t += dt
        ctrl.update()
        # CP Violation as menu music — falls back to drone if missing
        if not sfx.music_playing():
            cp = asset("02 CP Violation.mp3")
            if cp:
                sfx.play_music(cp, loops=-1, fade_ms=2000, volume=0.55)
            else:
                sfx.start_drone()
        if self.sel != self._prev_sel:
            if self._prev_sel != -1: sfx.play("tick")
            self._prev_sel = self.sel

    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        self._bg3d()

        surf = pygame.Surface((W, H), pygame.SRCALPHA)
        # Left panel
        p = pygame.Surface((310, H), pygame.SRCALPHA); p.fill((0,0,0,185))
        surf.blit(p, (0,0))

        txt2d(surf, "λ",    F_HUGE, C_LAMBDA, 52, 55)
        for i, ln in enumerate(["HALF","LIFE","0"]):
            txt2d(surf, ln, F_BIG, C_LAMBDA, 52, 170+i*36)

        flash = (math.sin(self.t*3)+1)/2
        for i,(label,_) in enumerate(self.ITEMS):
            y   = 330 + i*38
            sel = (i == self.sel)
            if label == "-BLUE SHIFT-":
                c = lerp_c(C_BLUE, C_WHITE, flash*0.2) if sel else C_BLUE
            else:
                c = C_WHITE if sel else C_LIGHT
            txt2d(surf, ("> " if sel else "  ")+label, F_MED, c, 48, y)

        # Subtitle bar
        sub = self.SUBS.get(self.ITEMS[self.sel][0], "")
        pygame.draw.rect(surf, (0,0,0,170), (0, H-46, W, 46))
        txt2d(surf, sub,                    F_SMALL, C_MUTED, W//2, H-23, anchor="center")
        txt2d(surf, ctrl.status_str(),      F_TINY,  C_MID,   W-10, H-10, anchor="bottomright")
        txt2d(surf, "HL0 PROTO  //  TCF 2026", F_TINY, C_MID, 10, H-10, anchor="bottomleft")
        notifier.draw(surf)
        draw_overlay(surf)

    def _bg3d(self):
        """Real Automation screenshot as menu background."""
        if self._bg is None:
            self._bg = load_gl_texture(asset("AutomationBuilding.png")) or False
        if self._bg:
            draw_fullscreen_tex(self._bg, alpha=1.0, fit="fill")
        else:
            # Fallback: solid dark
            glClearColor(0.07, 0.08, 0.06, 1)
            glClear(GL_COLOR_BUFFER_BIT)


# ══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN STATE (3D first-person)
# ══════════════════════════════════════════════════════════════════════════════
DOCS = [
    ("PROJECT OUROBOROS — MEMO 7",
     "Dimensional barrier in Sector C continues to degrade.\n"
     "Something is pushing from the other side. Has been for weeks.\n"
     "Dr. Kleiner insists it's instrument error. I disagree.",
     C_AMBER),
    ("APERTURE SCIENCE — INVOICE #4471",
     "RE: Crystal sample batch 7-G. Payment received.\n"
     "Shipment cleared customs as 'industrial lubricant'.\n"
     "Do not contact this office again.  — AP Logistics",
     C_PORTAL),
    ("SECURITY LOG — RESTRICTED",
     "Visitor badge: [REDACTED].  Duration: 4 hours.\n"
     "Access: Sub-levels 1-4, Lambda core, transit depot.\n"
     "Escorted by: nobody.  Badge returned. No footage.",
     C_RED),
    ("XEN SPECIMEN — BATCH 12",
     "Vortigaunt subject resists sedation at all dosages.\n"
     "Communicates in fragmented English. Repeating phrase:\n"
     "'The cascade is prepared. The man has prepared it.'",
     C_XEN),
    # ── Level 3: Tram Arrival ────────────────────────────────────────────────
    ("TRANSIT MANIFEST — ARRIVAL LOG 14-C",
     "Passenger manifest for tram 14-C shows 47 researchers.\n"
     "Security footage shows 46 disembarking. Badge #4471 never\n"
     "checked in. Badge was issued to: [REDACTED].  G-Man database.",
     (200, 160, 40)),
    ("PERSONNEL FILE — DR. YANG / DR. CROSS",
     "Both researchers last seen entering Sub-Level 4 at 06:14.\n"
     "Neither attended their 08:00 briefing. Keycard logs show\n"
     "both cards used in Lambda core at 06:58. No cameras there.",
     (80, 140, 200)),
    # ── Level 4: Aperture Science Wing ──────────────────────────────────────
    ("PORTAL DEVICE — PROTOTYPE REPORT",
     "Cave Johnson memo, dated 14 years prior to current date.\n"
     "'The portal prototype works. It works TOO well. We've been\n"
     "asked to destroy all records. We are not destroying records.'",
     (60, 180, 240)),
    ("APERTURE / BLACK MESA — JOINT MEMO",
     "Re: crystal sample exchange program.\n"
     "Aperture provides stabilisation compound.\n"
     "Black Mesa provides Xen resonance data. Both deny the other exists.",
     (60, 180, 240)),
    # ── Level 5: Xen Pocket ──────────────────────────────────────────────────
    ("XEN DATA CACHE — BIOLOGICAL SURVEY",
     "Specimen taxonomy incomplete. At least 40 distinct species.\n"
     "Vortigaunts demonstrate organised resistance to cataloguing.\n"
     "They are not livestock. They know what we are doing here.",
     (80, 200, 120)),
    ("XEN COMMUNICATION — TRANSLATED",
     "Fragment recovered from Vortigaunt subject 7.\n"
     "'The one in the suit walks between your moments.\n"
     "He has chosen the hour. The Freeman is the key, not the lock.'",
     (80, 200, 120)),
    # ── Level 6: Surface ─────────────────────────────────────────────────────
    ("PERIMETER LOG — SURVEILLANCE NODE 9",
     "Unknown vehicle observed 2.3km east, bearing 047.\n"
     "No transponder. No response to hails. Disappeared.\n"
     "Second observation same coordinates, 72hrs later. Same vehicle.",
     (160, 165, 150)),
    ("SATELLITE INTERCEPT — CLASSIFIED",
     "Signal origin: unknown orbital platform.\n"
     "Content: compressed data burst, Xen resonance frequencies.\n"
     "Decoded header: ADVISORY. CONVERGENCE IMMINENT. PREPARE PORTAL.",
     (200, 60, 40)),
    # ── Level 7: G-Man Corridor ──────────────────────────────────────────────
    ("FINAL MEMO — DR. VANCE TO LAMBDA TEAM",
     "If you are reading this, the cascade has begun or is beginning.\n"
     "The data is in the cache. Everything we found. The man in the suit\n"
     "let me leave this here. That alone terrifies me.",
     (140, 145, 130)),
    ("LAMBDA CACHE — UPLOAD CONFIRMATION",
     "Data integrity: 100%. Redundant copies: 7.\n"
     "Access key: FREEMAN.\n"
     "Note appended by unknown party: 'He will know what to do with it.'",
     (140, 145, 130)),
]

class CampaignState:
    def __init__(self, save_data=None):
        sd = save_data or default_save()
        self.level_idx   = sd.get("level", 0)
        self.health      = sd.get("health", 100)
        self.suit        = sd.get("suit", 100)
        self.doc_idx     = len(sd.get("docs_found", []))
        self.doc_found   = sd.get("docs_found", [])
        self.missions_done = set(sd.get("missions_done", []))
        self.xen_bleed   = sd.get("xen_bleed", 0.0)
        self._load_level(sd)
        self.active_doc  = None
        self.hud_msg     = ""; self.hud_t = 0.0
        self.interact_cd = 0.0
        self.t           = 0.0
        self.term_use_count = 0
        self.level_fade  = 0.0
        self._autosave_t = 0.0
        self.show_missions = False
        pygame.event.set_grab(True)
        pygame.mouse.set_visible(False)
        pygame.mouse.get_rel()   # flush

    def _load_level(self, sd=None):
        idx = self.level_idx
        self.tilemap = parse_level(idx)
        sx, sz, syaw = LEVEL_SPAWNS[idx]
        if sd and sd.get("level", 0) == idx and sd.get("pos"):
            sx, sz = sd["pos"]; syaw = sd.get("yaw", syaw)
        self.cam     = Camera(sx, sz, yaw=syaw)
        self.npcs    = self._spawn_npcs()
        rows         = LEVELS[idx]
        self.items   = [(rx, ry) for ry,row in enumerate(rows)
                        for rx,c in enumerate(row) if c=="I"]
        self.item_alive = {p: True for p in self.items}
        self.terms   = [(rx, ry) for ry,row in enumerate(rows)
                        for rx,c in enumerate(row) if c=="T"]
        self.exits   = find_exits(idx)
        self.missions = [m for m in build_missions(idx)
                         if m.id not in self.missions_done]
        self.term_use_count = 0
        self.gman = GManEncounter() if idx == 7 else None
        notifier.push(f"[HL0]  {LEVEL_NAMES[idx]}", C_AMBER, t=5.0)

    def _active_mission(self):
        for m in self.missions:
            if not m.done: return m
        return None

    GUARD_BARKS = [
        "HEY — stop right there!",
        "Unauthorized personnel detected!",
        "This area is restricted!",
        "I'm calling this in.",
        "Don't move!",
        "Security breach — sector C!",
    ]
    SCIENTIST_BARKS = [
        "Oh — hello. You shouldn't be here.",
        "This area is off-limits, I'm afraid.",
        "Have you cleared level 4? No? Then please leave.",
        "I'm going to have to report this.",
        "Good lord — who let you in?",
        "Please, I'm trying to work.",
    ]

    def _spawn_npcs(self):
        npcs = []
        rows = LEVELS[self.level_idx]
        for ry, row in enumerate(rows):
            for rx, c in enumerate(row):
                if c == "N":
                    npcs.append({
                        "x": rx+0.5, "z": ry+0.5,
                        "kind": random.choice(["guard","scientist"]),
                        "move_t": random.uniform(1,3),
                        "alert": 0.0,
                        "bark_cd": random.uniform(3,8),
                        "last_bark": "",
                    })
        return npcs

    def _save(self):
        done_ids = list(self.missions_done) + [m.id for m in self.missions if m.done]
        data = {"level": self.level_idx, "health": self.health, "suit": self.suit,
                "docs_found": self.doc_found, "missions_done": done_ids,
                "pos": [self.cam.x, self.cam.z], "yaw": self.cam.yaw,
                "xen_bleed": self.xen_bleed}
        if save_game(data):
            notifier.push("[SAVE] Game saved.", C_GREEN, t=2.5)
        else:
            notifier.push("[SAVE] Save failed!", C_RED, t=2.5)

    def _mission_event(self, etype, value):
        m = self._active_mission()
        if not m: return
        if m.check(etype, value):
            sfx.play("select")
            if m.done:
                notifier.push(f"[MISSION COMPLETE]  {m.title}", C_GREEN, t=5.0)
                self.missions_done.add(m.id)
                self._save()
            else:
                notifier.push(f"[MISSION]  {m.current_hint()}", C_AMBER, t=4.0)

    def handle(self, event):
        if self.active_doc:
            if event.type == KEYDOWN and event.key in (K_e, K_ESCAPE, K_RETURN):
                self.active_doc = None
            if event.type == JOYBUTTONDOWN: self.active_doc = None
            return
        if event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                sfx.play("tick")
                pygame.event.set_grab(False)
                pygame.mouse.set_visible(True)
                return "menu"
            if event.key == K_e:       self._interact()
            if event.key == K_m:
                grabbed = pygame.event.get_grab()
                pygame.event.set_grab(not grabbed)
                pygame.mouse.set_visible(grabbed)
                pygame.mouse.get_rel()  # flush delta
                notifier.push("[MOUSE] Look: " + ("ON" if not grabbed else "OFF"), C_MUTED, t=1.5)
            if event.key == K_TAB:     self.show_missions = not self.show_missions
            if event.key == K_F5:      self._save()
            if event.key == K_f:
                self.xen_bleed = min(1.0, self.xen_bleed+0.35)
                sfx.play("xen"); self._mission_event("xen_trigger", True)
        if event.type == JOYBUTTONDOWN:
            if event.button in (0,1):  self._interact()
            if ctrl.profile != "zero2" and event.button == 7: return "menu"
            if ctrl.profile == "zero2" and event.button == 8: return "menu"

    def _interact(self):
        if self.interact_cd > 0: return
        self.interact_cd = 0.5
        cx, cz = self.cam.x, self.cam.z
        for pos in self.items:
            if self.item_alive.get(pos):
                if math.hypot(cx-(pos[0]+0.5), cz-(pos[1]+0.5)) < 1.3:
                    self.item_alive[pos] = False
                    if self.doc_idx < len(DOCS):
                        doc = DOCS[self.doc_idx]
                        self.doc_found.append(self.doc_idx)
                        self.active_doc = doc
                        notifier.push(f"[SCAN] {doc[0][:36]}", doc[2])
                        sfx.play("scan")
                        self._mission_event("scan_doc", self.doc_idx)
                        self.doc_idx += 1
                    return
        for i, (tx, tz) in enumerate(self.terms):
            if math.hypot(cx-(tx+0.5), cz-(tz+0.5)) < 1.3:
                sfx.play("terminal")
                notifier.push(random.choice([
                    "ACCESS DENIED — CLEARANCE LEVEL 5 REQUIRED",
                    "SECTOR C — STABILITY 67%  SEE REPORT 7-G",
                    "LAMBDA COMPLEX — DIMENSIONAL BLEED DETECTED",
                    "NEXT TRAM DEPARTURE: 4 MINUTES",
                    "APERTURE SCIENCE INVOICE FLAGGED BY ACCOUNTING",
                    "POWER GRID OFFLINE — SECURITY PROTOCOLS SUSPENDED",
                    "XEN RESONANCE SPIKE — SECTOR D — EVACUATE",
                    "VORTIGAUNT CONTAINMENT BREACH — SUB-LEVEL 4",
                ]), C_AMBER)
                self._mission_event("use_terminal", self.term_use_count)
                self.term_use_count += 1
                return
        self.hud_msg = "Nothing nearby.  [E] interact  [TAB] missions  [F5] save"
        self.hud_t   = 2.5

    def update(self, dt):
        self.t += dt; self.hud_t = max(0, self.hud_t-dt)
        self.interact_cd = max(0, self.interact_cd-dt)
        self.xen_bleed   = max(0, self.xen_bleed - dt*0.05)
        ctrl.update()
        self._autosave_t += dt
        if self._autosave_t >= 60.0:
            self._autosave_t = 0.0; self._save()
        if not self.active_doc:
            self.cam.update(dt, pygame.key.get_pressed(), self.tilemap)
        for npc in self.npcs:
            npc["move_t"] -= dt
            if npc["move_t"] <= 0: npc["move_t"] = random.uniform(1,3)
            d = math.hypot(self.cam.x-npc["x"], self.cam.z-npc["z"])
            npc["alert"] = min(1,npc["alert"]+dt*0.3) if d<4.0 else max(0,npc["alert"]-dt*0.2)
            # Combat: fully-alert guards damage player
            if npc["kind"] == "guard" and npc["alert"] >= 1.0 and d < 3.5:
                self.health = max(0, self.health - int(6 * dt))
                if self.health <= 0:
                    notifier.push("[HL0] You have been neutralised. Reloading last save...", C_RED, t=4.0)
                    sd = load_game()
                    self._load_level(sd)
                    self.health = sd.get("health", 100) if sd else 100
            # Barks
            npc["bark_cd"] -= dt
            if npc["bark_cd"] <= 0 and npc["alert"] > 0.3 and d < 6.0:
                pool = self.GUARD_BARKS if npc["kind"] == "guard" else self.SCIENTIST_BARKS
                bark = random.choice(pool)
                notifier.push(f'[{npc["kind"].upper()}] "{bark}"',
                    C_RED if npc["kind"]=="guard" else C_MUTED, t=3.0)
                npc["bark_cd"] = random.uniform(5, 12)
        if self.level_fade <= 0:
            for ex, ez in self.exits:
                if math.hypot(self.cam.x-(ex+0.5), self.cam.z-(ez+0.5)) < 0.9:
                    self.level_fade = 0.01
                    notifier.push("[HL0] Entering next area...", C_LAMBDA, t=3.0)
        if self.level_fade > 0:
            self.level_fade += dt
            if self.level_fade >= 1.8:
                if self.level_idx + 1 < len(LEVELS):
                    self.level_idx += 1; self._save(); self._load_level()
                    self.level_fade = 0.0
                else:
                    notifier.push("[HL0] THE CASCADE BEGINS.  Eleanor sealed the cache.  Freeman is next.", C_XEN, t=10.0)
                    self.level_fade = 0.0
        if self.gman:
            self.gman.update(dt, self.cam.x, self.cam.z)
            if self.gman.total_seen > 0:
                self._mission_event("reach_tile", (20, 13))
        m = self._active_mission()
        if m and m.step < len(m.steps):
            s = m.steps[m.step]
            if s["type"] == "reach_tile":
                if math.hypot(self.cam.x-s["target"][0], self.cam.z-s["target"][1]) < 1.5:
                    self._mission_event("reach_tile", s["target"])

    def draw(self):
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluPerspective(FOV, W/H, NEAR, FAR)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.cam.apply()
        draw_level(self.tilemap)
        NPC_COL = {"guard":(200,80,40), "scientist":(80,140,200)}
        for npc in self.npcs:
            draw_billboard(npc["x"], npc["z"], NPC_COL[npc["kind"]], self.cam.x, self.cam.z)
        if self.gman:
            self.gman.draw(self.cam.x, self.cam.z)
        pulse = (math.sin(self.t*3)+1)/2
        for ex, ez in self.exits:
            br = 0.2 + pulse*0.5
            glBegin(GL_QUADS); glColor3f(0,br,0)
            glVertex3f(ex+0.1,0.02,ez+0.1); glVertex3f(ex+0.9,0.02,ez+0.1)
            glVertex3f(ex+0.9,0.02,ez+0.9); glVertex3f(ex+0.1,0.02,ez+0.9)
            glEnd()
        for pos in self.items:
            if self.item_alive.get(pos):
                x, z = pos[0]+0.5, pos[1]+0.5
                br = 0.3 + pulse*0.45
                glBegin(GL_QUADS); glColor3f(br, br*0.78, 0.0)
                glVertex3f(x-0.18,0.02,z-0.18); glVertex3f(x+0.18,0.02,z-0.18)
                glVertex3f(x+0.18,0.02,z+0.18); glVertex3f(x-0.18,0.02,z+0.18)
                glEnd()
        surf = pygame.Surface((W,H), pygame.SRCALPHA)
        if self.level_fade > 0:
            fa = min(1.0, self.level_fade/1.0)
            surf.fill((0,0,0,int(fa*255)))
            if fa > 0.5:
                s2 = F_BIG.render(LEVEL_NAMES[min(self.level_idx,len(LEVEL_NAMES)-1)], True, C_LAMBDA)
                surf.blit(s2, (W//2-s2.get_width()//2, H//2-s2.get_height()//2))
        self._hud(surf)
        if self.active_doc:    self._doc(surf)
        if self.show_missions: self._missions_panel(surf)
        notifier.draw(surf); draw_overlay(surf)

    def _hud(self, s):
        cx2, cy2 = W//2, H//2
        pygame.draw.line(s,(100,105,90,160),(cx2-8,cy2),(cx2+8,cy2),1)
        pygame.draw.line(s,(100,105,90,160),(cx2,cy2-8),(cx2,cy2+8),1)
        bw = 160
        pygame.draw.rect(s,(*C_DARK,200),(10,H-46,bw,12))
        pygame.draw.rect(s,(*C_RED, 200),(10,H-46,int(bw*self.health/100),12))
        txt2d(s,f"HP {self.health}", F_TINY,C_WHITE,10,H-49,anchor="bottomleft")
        pygame.draw.rect(s,(*C_DARK,200),(10,H-26,bw,12))
        pygame.draw.rect(s,(*C_BLUE,200),(10,H-26,int(bw*self.suit/100),12))
        txt2d(s,f"HEV {self.suit}%",F_TINY,C_LIGHT,10,H-28,anchor="bottomleft")
        txt2d(s,LEVEL_NAMES[self.level_idx],F_TINY,C_MUTED,W//2,10,anchor="midtop")
        txt2d(s,f"DOCS {len(self.doc_found)}/{len(DOCS)}",F_TINY,C_MUTED,W-10,H-28,anchor="bottomright")
        m = self._active_mission()
        if m:
            pygame.draw.rect(s,(0,0,0,140),(W//2-260,28,520,28))
            txt2d(s,f"  {m.title}:  {m.current_hint()}",F_TINY,C_AMBER,W//2,42,anchor="center")
        hint = "[W/S] MOVE  [A/D] STRAFE  [←→] TURN  [E] INTERACT  [F] XEN  [TAB] MISSIONS  [F5] SAVE  [ESC] MENU"
        txt2d(s,hint,F_TINY,C_MID,W//2,H-8,anchor="midbottom")
        if self.xen_bleed > 0.01:
            ov = pygame.Surface((W,H),pygame.SRCALPHA)
            ov.fill((80,200,120,int(self.xen_bleed*55))); s.blit(ov,(0,0))
            txt2d(s,f"DIMENSIONAL BLEED {int(self.xen_bleed*100)}%",F_SMALL,C_XEN,W//2,22,anchor="midtop")
        if self.hud_t > 0:
            txt2d(s,self.hud_msg,F_SMALL,C_LIGHT,W//2,H//2+70,anchor="center")

        # Minimap — top-right corner
        self._minimap(s)

    def _minimap(self, s):
        MM = 3        # pixels per tile
        PAD = 12
        rows = len(self.tilemap)
        cols = max(len(r) for r in self.tilemap)
        mw = cols * MM; mh = rows * MM
        ox = W - mw - PAD; oy = PAD
        # Background
        bg = pygame.Surface((mw, mh), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        s.blit(bg, (ox, oy))
        # Tiles
        TILE_COLS = {
            T_FLOOR:  (55, 60, 50),
            T_WALL:   (0, 0, 0),
            T_DOOR:   (40, 90, 120),
            T_VENT:   (60, 75, 55),
            T_TERM:   (40, 80, 160),
            T_ITEM:   (160, 140, 40),
            T_NPC:    (55, 60, 50),
            T_APT:    (200, 200, 210),
            T_XEN:    (20, 80, 60),
            T_GLASS:  (80, 120, 160),
        }
        for ry, row in enumerate(self.tilemap):
            for rx, tile in enumerate(row):
                c = TILE_COLS.get(tile, (40, 40, 40))
                pygame.draw.rect(s, c, (ox + rx*MM, oy + ry*MM, MM, MM))
        # Exits — green dots
        for ex, ez in self.exits:
            pygame.draw.rect(s, (60, 200, 80),
                             (ox + ex*MM, oy + ez*MM, MM, MM))
        # Docs — yellow dots
        for pos in self.items:
            if self.item_alive.get(pos):
                pygame.draw.rect(s, (200, 160, 40),
                                 (ox + pos[0]*MM, oy + pos[1]*MM, MM, MM))
        # NPCs — red/blue dots
        for npc in self.npcs:
            c = (200, 60, 40) if npc["kind"] == "guard" else (60, 120, 200)
            nx = int(npc["x"]) * MM; nz = int(npc["z"]) * MM
            pygame.draw.rect(s, c, (ox + nx, oy + nz, MM, MM))
        # Player — white dot
        px = int(self.cam.x) * MM; pz = int(self.cam.z) * MM
        pygame.draw.rect(s, (255, 255, 255), (ox + px, oy + pz, MM+1, MM+1))
        # Border
        pygame.draw.rect(s, C_MUTED, (ox, oy, mw, mh), 1)
        txt2d(s, "MAP", F_TINY, C_MID, ox, oy + mh + 2, anchor="topleft")

    def _doc(self, s):
        doc = self.active_doc
        ov = pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,200)); s.blit(ov,(0,0))
        pw,ph = 580,300; px,py = (W-pw)//2,(H-ph)//2
        pygame.draw.rect(s,(20,24,16,245),(px,py,pw,ph))
        pygame.draw.rect(s,(*doc[2],220),(px,py,pw,ph),1)
        txt2d(s,"// CLASSIFIED //",F_TINY,C_MUTED,px+pw//2,py+10,anchor="midtop")
        txt2d(s,doc[0],F_MED,doc[2],px+18,py+28)
        pygame.draw.line(s,C_DARK,(px+18,py+56),(px+pw-18,py+56))
        y = py+70
        for ln in doc[1].split("\n"):
            txt2d(s,ln,F_SMALL,C_LIGHT,px+18,y); y+=22
        txt2d(s,"[E / ENTER / ESC]  CLOSE",F_TINY,C_MUTED,px+pw//2,py+ph-12,anchor="midbottom")

    def _missions_panel(self, s):
        ov = pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,180)); s.blit(ov,(0,0))
        pw = 500; ph = min(60+len(self.missions)*70+30, H-80)
        px,py = (W-pw)//2,(H-ph)//2
        pygame.draw.rect(s,(16,20,13,230),(px,py,pw,ph))
        pygame.draw.rect(s,(*C_LAMBDA,200),(px,py,pw,ph),1)
        txt2d(s,"MISSIONS",F_BIG,C_LAMBDA,px+pw//2,py+14,anchor="midtop")
        y = py+52
        for m in self.missions:
            c = C_GREEN if m.done else C_AMBER
            status = "COMPLETE" if m.done else m.current_hint()
            pygame.draw.rect(s,(25,32,20,180),(px+10,y,pw-20,60))
            pygame.draw.rect(s,(*c,120),(px+10,y,pw-20,60),1)
            txt2d(s,m.title, F_SMALL,c,     px+20,y+8)
            txt2d(s,m.desc,  F_TINY,C_MUTED,px+20,y+26)
            txt2d(s,status,  F_TINY,c,      px+20,y+42)
            y += 68
            if y > py+ph-20: break
        txt2d(s,"[TAB]  CLOSE",F_TINY,C_MID,px+pw//2,py+ph-12,anchor="midbottom")


# ══════════════════════════════════════════════════════════════════════════════
# SANDBOX STATE (3D physics room)
# ══════════════════════════════════════════════════════════════════════════════
SB_TYPES = [
    ("HEADCRAB",    (140,100,60),  (0.40,0.30,0.40)),
    ("SCIENTIST",   (80, 140,200), (0.28,0.70,0.28)),
    ("GUARD",       (200,80, 40),  (0.28,0.70,0.28)),
    ("CRATE",       (120,90, 50),  (0.55,0.55,0.55)),
    ("VORTIGAUNT",  (80, 200,120), (0.32,0.80,0.32)),
    ("ADVISOR",     (60, 60, 100), (0.60,0.50,0.60)),
    ("PORTAL SHARD",(60, 180,240), (0.22,0.40,0.22)),
    ("XEN CRYSTAL", (120,255,160), (0.18,0.60,0.18)),
]
ROOM = 18.0; CEIL = 5.0

class SBEntity:
    _id = 0
    def __init__(self, ki, x, z):
        SBEntity._id += 1
        self.eid = SBEntity._id
        self.kind = SB_TYPES[ki]
        hw,hh,hd = [v/2 for v in self.kind[2]]
        self.hw,self.hh,self.hd = hw,hh,hd
        self.x = float(x); self.y = CEIL*0.5; self.z = float(z)
        self.vx = random.uniform(-3,3); self.vy = random.uniform(1,5)
        self.vz = random.uniform(-3,3)

    def update(self, dt):
        self.vy -= 10.0*dt
        self.x += self.vx*dt; self.y += self.vy*dt; self.z += self.vz*dt
        hw = ROOM/2
        if self.y-self.hh <= 0:
            self.y = self.hh; self.vy = -self.vy*0.38
            self.vx *= 0.78; self.vz *= 0.78
        if self.y+self.hh >= CEIL: self.y = CEIL-self.hh; self.vy = -abs(self.vy)*0.4
        if abs(self.x)+self.hw > hw: self.vx=-self.vx*0.65; self.x=math.copysign(hw-self.hw,self.x)
        if abs(self.z)+self.hd > hw: self.vz=-self.vz*0.65; self.z=math.copysign(hw-self.hd,self.z)

    def draw(self):
        hw,hh,hd = self.hw,self.hh,self.hd
        c = [v/255.0 for v in self.kind[1]]
        dk = [v*0.58 for v in c]
        md = [v*0.78 for v in c]
        glPushMatrix(); glTranslatef(self.x,self.y,self.z)
        glBegin(GL_QUADS)
        glColor3f(*c)   # top
        glVertex3f(-hw,hh,-hd);glVertex3f(hw,hh,-hd);glVertex3f(hw,hh,hd);glVertex3f(-hw,hh,hd)
        glColor3f(*dk)  # bottom
        glVertex3f(-hw,-hh,hd);glVertex3f(hw,-hh,hd);glVertex3f(hw,-hh,-hd);glVertex3f(-hw,-hh,-hd)
        glColor3f(*c)   # front
        glVertex3f(-hw,-hh,hd);glVertex3f(hw,-hh,hd);glVertex3f(hw,hh,hd);glVertex3f(-hw,hh,hd)
        glColor3f(*dk)  # back
        glVertex3f(hw,-hh,-hd);glVertex3f(-hw,-hh,-hd);glVertex3f(-hw,hh,-hd);glVertex3f(hw,hh,-hd)
        glColor3f(*md)  # left
        glVertex3f(-hw,-hh,-hd);glVertex3f(-hw,-hh,hd);glVertex3f(-hw,hh,hd);glVertex3f(-hw,hh,-hd)
        glColor3f(*md)  # right
        glVertex3f(hw,-hh,hd);glVertex3f(hw,-hh,-hd);glVertex3f(hw,hh,-hd);glVertex3f(hw,hh,hd)
        glEnd(); glPopMatrix()


class SandboxState:
    def __init__(self):
        self.cam        = Camera(0.0, 5.0, yaw=0.0, height=1.8)
        self.entities   = []
        self.spawn_sel  = 0
        self.spawn_open = False
        self.t          = 0.0
        for i in range(5):
            self.entities.append(SBEntity(i%len(SB_TYPES),
                random.uniform(-4,4), random.uniform(-4,4)))

    def handle(self, event):
        if event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                if self.spawn_open: self.spawn_open = False
                else: return "menu"
            if event.key in (K_q, K_TAB): self.spawn_open = not self.spawn_open
            if self.spawn_open:
                if event.key == K_UP:   self.spawn_sel=(self.spawn_sel-1)%len(SB_TYPES)
                if event.key == K_DOWN: self.spawn_sel=(self.spawn_sel+1)%len(SB_TYPES)
                if event.key == K_RETURN: self._spawn()
            if event.key in (K_DELETE, K_x):
                if self.entities: self.entities.pop(); sfx.play("tick")
        if event.type == JOYHATMOTION and self.spawn_open:
            v = event.value
            if v[1]==1:  self.spawn_sel=(self.spawn_sel-1)%len(SB_TYPES)
            if v[1]==-1: self.spawn_sel=(self.spawn_sel+1)%len(SB_TYPES)
        if event.type == JOYBUTTONDOWN:
            is_z2 = ctrl.profile=="zero2"
            if (is_z2 and event.button==1) or (not is_z2 and event.button==0):
                if self.spawn_open: self._spawn()
                else: self.spawn_open = True
            if (is_z2 and event.button==8) or (not is_z2 and event.button==7): return "menu"
            if not is_z2 and event.button==2:  # X button throws entity
                if self.entities: self.entities[-1].vx=random.uniform(-6,6); self.entities[-1].vy=8

    def _spawn(self):
        fx, fz = self.cam.fwd()
        e = SBEntity(self.spawn_sel, self.cam.x+fx*2.5, self.cam.z+fz*2.5)
        e.vx=fx*6; e.vz=fz*6; e.vy=4
        self.entities.append(e)
        notifier.push(f"[SANDBOX] Spawned {SB_TYPES[self.spawn_sel][0]}", C_GREEN)
        sfx.play("select")
        self.spawn_open = False

    def update(self, dt):
        self.t += dt; ctrl.update()
        keys = pygame.key.get_pressed()
        # Flat ground, no walls in sandbox
        self.cam.update(dt, keys, [[T_FLOOR]*40]*40)
        hw = ROOM/2-0.4
        self.cam.x = max(-hw, min(hw, self.cam.x))
        self.cam.z = max(-hw, min(hw, self.cam.z))
        for e in self.entities: e.update(dt)

    def draw(self):
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluPerspective(FOV, W/H, NEAR, FAR)
        glMatrixMode(GL_MODELVIEW); glLoadIdentity()
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.cam.apply()
        self._room()
        for e in self.entities: e.draw()

        surf = pygame.Surface((W,H),pygame.SRCALPHA)
        self._hud(surf)
        if self.spawn_open: self._spawn_menu(surf)
        notifier.draw(surf); draw_overlay(surf)

    def _room(self):
        hw = ROOM/2
        glBegin(GL_QUADS)
        for ix in range(int(-hw), int(hw)):
            for iz in range(int(-hw), int(hw)):
                c = (0.12,0.14,0.09) if (ix+iz)%2==0 else (0.10,0.12,0.07)
                glColor3f(*c)
                glVertex3f(ix,  0,iz  );glVertex3f(ix+1,0,iz  )
                glVertex3f(ix+1,0,iz+1);glVertex3f(ix,  0,iz+1)
        glColor3f(0.09,0.10,0.07)  # ceiling
        glVertex3f(-hw,CEIL,-hw);glVertex3f(hw,CEIL,-hw);glVertex3f(hw,CEIL,hw);glVertex3f(-hw,CEIL,hw)
        wc=(0.22,0.25,0.18); dk=(0.16,0.18,0.13)
        glColor3f(*wc)
        glVertex3f(-hw,0,-hw);glVertex3f(hw,0,-hw);glVertex3f(hw,CEIL,-hw);glVertex3f(-hw,CEIL,-hw)
        glVertex3f(hw,0,hw);glVertex3f(-hw,0,hw);glVertex3f(-hw,CEIL,hw);glVertex3f(hw,CEIL,hw)
        glColor3f(*dk)
        glVertex3f(hw,0,-hw);glVertex3f(hw,0,hw);glVertex3f(hw,CEIL,hw);glVertex3f(hw,CEIL,-hw)
        glVertex3f(-hw,0,hw);glVertex3f(-hw,0,-hw);glVertex3f(-hw,CEIL,-hw);glVertex3f(-hw,CEIL,hw)
        glEnd()

    def _hud(self, s):
        cx2,cy2=W//2,H//2
        pygame.draw.line(s,(100,105,90,140),(cx2-6,cy2),(cx2+6,cy2),1)
        pygame.draw.line(s,(100,105,90,140),(cx2,cy2-6),(cx2,cy2+6),1)
        txt2d(s,"SANDBOX",F_BIG,C_LAMBDA,W//2,10,anchor="midtop")
        txt2d(s,f"ENTITIES: {len(self.entities)}",F_SMALL,C_MUTED,W-10,10,anchor="topright")
        hint = "[W/S] MOVE  [A/D] STRAFE  [←→] TURN  [Q] SPAWN  [DEL] REMOVE  [ESC] MENU"
        if ctrl.connected: hint += f"   [{ctrl.profile.upper()}] A=SPAWN  START=MENU"
        txt2d(s,hint,F_TINY,C_MID,W//2,H-8,anchor="midbottom")

    def _spawn_menu(self, s):
        pw,ph = 260, len(SB_TYPES)*30+50
        px,py = W//2-pw//2, H//2-ph//2
        pygame.draw.rect(s,(16,20,13,225),(px,py,pw,ph))
        pygame.draw.rect(s,(*C_LAMBDA,210),(px,py,pw,ph),1)
        txt2d(s,"SPAWN ENTITY",F_MED,C_LAMBDA,px+pw//2,py+10,anchor="midtop")
        for i,(name,col,_) in enumerate(SB_TYPES):
            y2=py+38+i*30; sel=(i==self.spawn_sel)
            c = lerp_c(col,C_WHITE,0.4) if sel else C_MUTED
            if sel: pygame.draw.rect(s,(30,38,22,180),(px+4,y2-2,pw-8,26))
            pygame.draw.rect(s,col,(px+12,y2+5,16,15))
            txt2d(s,name,F_SMALL,c,px+36,y2+10,anchor="midleft")
        txt2d(s,"[↑↓] SEL  [ENTER/A] SPAWN  [Q] CLOSE",F_TINY,C_MID,px+pw//2,py+ph-10,anchor="midbottom")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════
def main():
    init_gl()
    list_dir_assets()   # print what's in the folder
    STATES = {
        "boot":     BootState,
        "menu":     MenuState,
        "campaign": CampaignState,
        "sandbox":  SandboxState,
    }
    current = "boot"
    state   = BootState()

    while True:
        dt = min(clock.tick(FPS)/1000.0, 0.05)
        ctrl.update()

        for event in pygame.event.get():
            if event.type == QUIT:
                sfx.stop_drone(0); pygame.quit(); sys.exit()

            result = state.handle(event)

            if result == "quit":
                sfx.stop_drone(0); pygame.quit(); sys.exit()
            elif result in ("campaign", "campaign_continue"):
                sfx.stop_transit()
                sd = load_game() if result == "campaign_continue" else None
                current = "campaign"
                state   = CampaignState(save_data=sd)
                notifier.push("HL0  >  CAMPAIGN", C_LAMBDA)
            elif result in STATES:
                if current in ("boot","menu") and result not in ("boot","menu"):
                    sfx.stop_transit()
                if result == "menu": sfx.start_drone()
                current = result
                state   = STATES[result]()
                if result != "boot":
                    notifier.push(f"HL0  >  {result.upper()}", C_LAMBDA)

        result = state.update(dt)
        if result == "quit":
            sfx.stop_drone(0); pygame.quit(); sys.exit()
        elif result in ("campaign", "campaign_continue"):
            sfx.stop_transit()
            sd = load_game() if result == "campaign_continue" else None
            current = "campaign"
            state   = CampaignState(save_data=sd)
            notifier.push("HL0  >  CAMPAIGN", C_LAMBDA)
        elif result in STATES:
            if current in ("boot","menu") and result not in ("boot","menu"):
                sfx.stop_transit()
            if result == "menu": sfx.start_drone()
            current = result
            state   = STATES[result]()
            if result != "boot":
                notifier.push(f"HL0  >  {result.upper()}", C_LAMBDA)

        notifier.update(dt)
        state.draw()
        notifier.draw_gl()
        pygame.display.flip()

if __name__ == "__main__":
    main()
