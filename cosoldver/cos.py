#!/usr/bin/env python3
"""
COS — Channel Operating System
A TTY-native shell with mouse support and retro menubar.
Run in a real TTY or any terminal with mouse support.
"""

import curses
import curses.textpad
import os
import sys
import signal
import subprocess
import platform
from datetime import datetime

# ── Palette ──────────────────────────────────────────────────────────────────
CP_MENUBAR   = 1   # top bar
CP_MENU_SEL  = 2   # highlighted menu item
CP_DESKTOP   = 3   # background
CP_WINDOW    = 4   # window chrome
CP_WIN_TITLE = 5   # window title bar
CP_STATUS    = 6   # bottom status bar
CP_CURSOR    = 7   # mouse cursor indicator
CP_TEXT      = 8   # normal text in panes
CP_BRIGHT    = 9   # bright accent
CP_SHADOW    = 10  # shadow / dim

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(CP_MENUBAR,   curses.COLOR_BLACK,  curses.COLOR_CYAN)
    curses.init_pair(CP_MENU_SEL,  curses.COLOR_BLACK,  curses.COLOR_WHITE)
    curses.init_pair(CP_DESKTOP,   curses.COLOR_CYAN,   curses.COLOR_BLUE)
    curses.init_pair(CP_WINDOW,    curses.COLOR_WHITE,  curses.COLOR_BLACK)
    curses.init_pair(CP_WIN_TITLE, curses.COLOR_BLACK,  curses.COLOR_WHITE)
    curses.init_pair(CP_STATUS,    curses.COLOR_BLACK,  curses.COLOR_CYAN)
    curses.init_pair(CP_CURSOR,    curses.COLOR_BLACK,  curses.COLOR_YELLOW)
    curses.init_pair(CP_TEXT,      curses.COLOR_WHITE,  curses.COLOR_BLACK)
    curses.init_pair(CP_BRIGHT,    curses.COLOR_YELLOW, curses.COLOR_BLUE)
    curses.init_pair(CP_SHADOW,    curses.COLOR_BLACK,  curses.COLOR_BLUE)

# ── Menu definitions ──────────────────────────────────────────────────────────
MENUS = {
    'f': {
        'label': 'FILE',
        'key':   'f',
        'items': [
            ('New Session',   'new_session'),
            ('Open Terminal', 'open_term'),
            ('───────────',  None),
            ('Save Log',      'save_log'),
            ('───────────',  None),
            ('Exit COS',      'exit'),
        ]
    },
    'e': {
        'label': 'EDIT',
        'key':   'e',
        'items': [
            ('Copy',          'copy'),
            ('Paste',         'paste'),
            ('───────────',  None),
            ('Clear Screen',  'clear'),
            ('───────────',  None),
            ('Preferences',   'prefs'),
        ]
    },
    'a': {
        'label': 'APPS',
        'key':   'a',
        'items': [
            ('System Info',   'sysinfo'),
            ('File Browser',  'filebrowser'),
            ('───────────',  None),
            ('Calculator',    'calc'),
            ('Clock',         'clock'),
            ('───────────',  None),
            ('About COS',     'about'),
        ]
    },
    'c': {
        'label': 'CONTROL',
        'key':   'c',
        'items': [
            ('Processes',     'processes'),
            ('Disk Usage',    'disk'),
            ('───────────',  None),
            ('Network',       'network'),
            ('───────────',  None),
            ('Settings',      'settings'),
        ]
    },
    'p': {
        'label': 'POWER',
        'key':   'p',
        'items': [
            ('Restart Shell', 'restart'),
            ('───────────',  None),
            ('Suspend',       'suspend'),
            ('Reboot',        'reboot'),
            ('Shutdown',      'shutdown'),
        ]
    },
    'o': {
        'label': 'OTHER',
        'key':   'o',
        'items': [
            ('Help',          'help'),
            ('Keyboard Map',  'keymap'),
            ('───────────',  None),
            ('Credits',       'credits'),
        ]
    },
}

MENU_ORDER = ['f', 'e', 'a', 'c', 'p', 'o']

# ── Popup window ─────────────────────────────────────────────────────────────
class PopupWindow:
    def __init__(self, stdscr, title, lines, width=None):
        self.stdscr = stdscr
        self.title  = title
        self.lines  = lines
        H, W        = stdscr.getmaxyx()
        self.h      = min(len(lines) + 4, H - 4)
        self.w      = width or min(max(len(l) for l in lines) + 6, W - 4)
        self.y      = (H - self.h) // 2
        self.x      = (W - self.w) // 2

    def draw(self):
        win = curses.newwin(self.h, self.w, self.y, self.x)
        win.bkgd(' ', curses.color_pair(CP_WINDOW))
        win.border()
        title = f' {self.title} '
        win.addstr(0, (self.w - len(title)) // 2, title,
                   curses.color_pair(CP_WIN_TITLE) | curses.A_BOLD)
        for i, line in enumerate(self.lines[:self.h - 4]):
            win.addstr(i + 2, 2, line[:self.w - 4], curses.color_pair(CP_TEXT))
        hint = '[ press any key to close ]'
        win.addstr(self.h - 1, (self.w - len(hint)) // 2, hint,
                   curses.color_pair(CP_STATUS))
        win.refresh()
        win.getch()

# ── Dropdown menu ─────────────────────────────────────────────────────────────
class Dropdown:
    def __init__(self, stdscr, menu_key, col_x):
        self.stdscr   = stdscr
        self.menu_def = MENUS[menu_key]
        self.items    = self.menu_def['items']
        self.col_x    = col_x
        self.selected = 0
        H, W          = stdscr.getmaxyx()
        self.h        = len(self.items) + 2
        self.w        = max(len(i[0]) for i in self.items) + 4
        self.y        = 1
        self.x        = min(col_x, W - self.w - 1)

    def draw(self, sel):
        win = curses.newwin(self.h, self.w, self.y, self.x)
        win.bkgd(' ', curses.color_pair(CP_WINDOW))
        win.border()
        for i, (label, action) in enumerate(self.items):
            attr = curses.color_pair(CP_MENU_SEL) | curses.A_BOLD if i == sel \
                   else curses.color_pair(CP_TEXT)
            if action is None:
                win.addstr(i + 1, 1, label[:self.w - 2], curses.color_pair(CP_SHADOW))
            else:
                win.addstr(i + 1, 1, f' {label:<{self.w-4}} ', attr)
        win.refresh()
        return win

    def run(self):
        """Run the dropdown interaction. Returns selected action or None."""
        sel = 0
        # skip separators on start
        while self.items[sel][1] is None:
            sel += 1
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        while True:
            win = self.draw(sel)
            key = self.stdscr.getch()
            if key == curses.KEY_MOUSE:
                try:
                    _, mx, my, _, bstate = curses.getmouse()
                    # click inside dropdown?
                    if self.y < my < self.y + self.h - 1 and \
                       self.x < mx < self.x + self.w - 1:
                        row = my - self.y - 1
                        if 0 <= row < len(self.items) and self.items[row][1]:
                            return self.items[row][1]
                    else:
                        return None  # click outside closes
                except curses.error:
                    pass
            elif key == curses.KEY_UP:
                sel = (sel - 1) % len(self.items)
                while self.items[sel][1] is None:
                    sel = (sel - 1) % len(self.items)
            elif key == curses.KEY_DOWN:
                sel = (sel + 1) % len(self.items)
                while self.items[sel][1] is None:
                    sel = (sel + 1) % len(self.items)
            elif key in (curses.KEY_ENTER, 10, 13):
                return self.items[sel][1]
            elif key == 27:  # ESC
                return None

# ── Action handlers ───────────────────────────────────────────────────────────
def handle_action(action, stdscr, state):
    H, W = stdscr.getmaxyx()

    if action == 'exit':
        state['running'] = False

    elif action == 'about':
        lines = [
            '  COS — Channel Operating System',
            '  Version 1.0 — TTY Native Shell',
            '',
            '  Part of the TCF (The Creative Force)',
            '  ecosystem. Built for real TTYs with',
            '  full mouse and keyboard support.',
            '',
            '  "The channel is always open."',
        ]
        PopupWindow(stdscr, 'About COS', lines, 42).draw()

    elif action == 'help':
        lines = [
            '  KEYBOARD SHORTCUTS',
            '  ──────────────────',
            '  F  — File menu',
            '  E  — Edit menu',
            '  A  — Apps menu',
            '  C  — Control menu',
            '  P  — Power menu',
            '  O  — Other menu',
            '',
            '  MOUSE',
            '  ─────',
            '  Click menu bar items to open menus',
            '  Click desktop to place cursor',
            '  Scroll to adjust desktop view',
            '',
            '  ESC / Q  — quit open menus',
        ]
        PopupWindow(stdscr, 'Help', lines, 44).draw()

    elif action == 'sysinfo':
        uname = platform.uname()
        now   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines = [
            f'  Node   : {uname.node}',
            f'  OS     : {uname.system} {uname.release}',
            f'  Arch   : {uname.machine}',
            f'  Python : {platform.python_version()}',
            f'  TTY    : {os.ttyname(0) if os.isatty(0) else "n/a"}',
            f'  Size   : {W}×{H} cols×rows',
            f'  Time   : {now}',
        ]
        PopupWindow(stdscr, 'System Info', lines, 48).draw()

    elif action == 'keymap':
        lines = [
            '  Q / ESC       close menus / quit COS',
            '  F E A C P O   open menu by letter',
            '  Arrow keys    navigate menus',
            '  Enter         select menu item',
            '  Mouse click   open menus, select items',
            '  Mouse move    move cursor on desktop',
        ]
        PopupWindow(stdscr, 'Key Map', lines, 50).draw()

    elif action == 'credits':
        lines = [
            '',
            '  Built by TCF — The Creative Force',
            '  Running on Channel Operating System',
            '',
            '  Powered by Python + curses',
            '  Mouse via GPM / xterm protocol',
            '',
        ]
        PopupWindow(stdscr, 'Credits', lines, 42).draw()

    elif action == 'clear':
        state['messages'].clear()

    elif action == 'processes':
        try:
            out = subprocess.check_output(['ps', 'aux', '--no-headers'],
                                          text=True, timeout=3)
            procs = out.strip().split('\n')[:min(20, H - 10)]
            lines = [f'  {p[:W - 8]}' for p in procs]
        except Exception as e:
            lines = [f'  Error: {e}']
        PopupWindow(stdscr, 'Processes', lines, min(W - 4, 80)).draw()

    elif action == 'disk':
        try:
            out = subprocess.check_output(['df', '-h'], text=True, timeout=3)
            lines = [f'  {l}' for l in out.strip().split('\n')]
        except Exception as e:
            lines = [f'  Error: {e}']
        PopupWindow(stdscr, 'Disk Usage', lines, min(W - 4, 72)).draw()

    elif action == 'clock':
        lines = [
            '',
            '  ' + datetime.now().strftime('  %A, %B %d %Y'),
            '',
            '  ' + datetime.now().strftime('     %H:%M:%S'),
            '',
        ]
        PopupWindow(stdscr, 'COS Clock', lines, 38).draw()

    elif action in ('reboot', 'shutdown', 'suspend'):
        lines = [
            f'  System {action} requires root / systemd.',
            '  Run this command from a normal shell.',
        ]
        PopupWindow(stdscr, f'Power: {action.title()}', lines, 50).draw()

    elif action == 'restart':
        state['messages'].append('[COS] Restarting shell session...')

    elif action == 'new_session':
        state['messages'].append('[COS] New session spawned.')

    elif action == 'open_term':
        state['messages'].append('[COS] Terminal: you are already in one.')

    elif action == 'save_log':
        fname = '/tmp/cos_session.log'
        try:
            with open(fname, 'w') as f:
                f.write('\n'.join(state['messages']))
            state['messages'].append(f'[COS] Log saved to {fname}')
        except Exception as e:
            state['messages'].append(f'[COS] Save failed: {e}')

    elif action == 'filebrowser':
        try:
            entries = sorted(os.listdir(os.path.expanduser('~')))[:30]
            lines   = [f'  {e}' for e in entries]
        except Exception as e:
            lines = [f'  Error: {e}']
        PopupWindow(stdscr, 'Home Directory', lines, 48).draw()

    elif action == 'network':
        try:
            out = subprocess.check_output(['ip', 'addr'], text=True, timeout=3)
            lines = [f'  {l}' for l in out.strip().split('\n')[:25]]
        except Exception:
            try:
                out = subprocess.check_output(['ifconfig'], text=True, timeout=3)
                lines = [f'  {l}' for l in out.strip().split('\n')[:25]]
            except Exception as e:
                lines = [f'  Error: {e}']
        PopupWindow(stdscr, 'Network', lines, min(W - 4, 70)).draw()

    elif action in ('copy', 'paste', 'prefs', 'settings', 'calc'):
        lines = [f'  [{action.upper()}] — not yet implemented in this build.']
        PopupWindow(stdscr, action.title(), lines, 48).draw()

# ── Desktop drawing ───────────────────────────────────────────────────────────
DESKTOP_LOGO = [
    r"  ╔═══════════════════════╗",
    r"  ║  COS  ·  v1.0  ·  TCF ║",
    r"  ╚═══════════════════════╝",
]

def draw_desktop(stdscr, H, W):
    stdscr.bkgd('·', curses.color_pair(CP_DESKTOP))
    stdscr.clear()
    # center logo
    ly = H // 2 - 2
    for i, line in enumerate(DESKTOP_LOGO):
        x = max(0, (W - len(line)) // 2)
        try:
            stdscr.addstr(ly + i, x, line,
                          curses.color_pair(CP_BRIGHT) | curses.A_BOLD)
        except curses.error:
            pass

def draw_menubar(stdscr, W, active_key=None):
    bar = ' COS (Channel Operating System)  ═  '
    segments = []
    col = len(bar)
    positions = {}
    for k in MENU_ORDER:
        m = MENUS[k]
        label = f' {m["label"]} [{m["key"]}] '
        positions[k] = col
        segments.append((label, k))
        col += len(label) + 3  # for ' ═ '

    try:
        stdscr.addstr(0, 0, ' ' * W, curses.color_pair(CP_MENUBAR))
        stdscr.addstr(0, 0, bar, curses.color_pair(CP_MENUBAR) | curses.A_BOLD)
        cx = len(bar)
        for i, (label, k) in enumerate(segments):
            attr = (curses.color_pair(CP_MENU_SEL) | curses.A_BOLD) \
                   if k == active_key else \
                   (curses.color_pair(CP_MENUBAR) | curses.A_BOLD)
            stdscr.addstr(0, cx, label, attr)
            cx += len(label)
            if i < len(segments) - 1:
                stdscr.addstr(0, cx, ' ═ ', curses.color_pair(CP_MENUBAR))
                cx += 3
    except curses.error:
        pass
    return positions

def draw_statusbar(stdscr, H, W, mouse_pos, msg=''):
    now = datetime.now().strftime('%H:%M:%S')
    mx, my = mouse_pos
    left  = f' COS  |  MOUSE ({mx:>3},{my:>3})  |  {msg}'
    right = f' {now} '
    pad   = W - len(left) - len(right)
    line  = left + ' ' * max(0, pad) + right
    try:
        stdscr.addstr(H - 1, 0, line[:W], curses.color_pair(CP_STATUS) | curses.A_BOLD)
    except curses.error:
        pass

def draw_messages(stdscr, H, W, messages):
    max_msgs = H - 6
    shown    = messages[-max_msgs:] if len(messages) > max_msgs else messages
    for i, msg in enumerate(shown):
        y = H - 2 - len(shown) + i
        if 2 <= y < H - 1:
            try:
                stdscr.addstr(y, 2, msg[:W - 4],
                              curses.color_pair(CP_TEXT) | curses.A_DIM)
            except curses.error:
                pass

def draw_cursor_dot(stdscr, H, W, mx, my):
    if 1 < my < H - 1 and 0 <= mx < W:
        try:
            stdscr.addstr(my, mx, '✛',
                          curses.color_pair(CP_CURSOR) | curses.A_BOLD)
        except curses.error:
            try:
                stdscr.addstr(my, mx, '+',
                              curses.color_pair(CP_CURSOR) | curses.A_BOLD)
            except curses.error:
                pass

# ── Main loop ─────────────────────────────────────────────────────────────────
def main(stdscr):
    curses.cbreak()
    curses.noecho()
    stdscr.keypad(True)
    curses.curs_set(0)

    # Enable mouse — ALL_MOUSE_EVENTS + REPORT_MOUSE_POSITION gives motion too
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    # xterm extended mouse (position tracking beyond col 223)
    print('\033[?1003h', end='', flush=True)
    # Also try to enable GPM if in real TTY
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        try:
            os.system('modprobe mousedev 2>/dev/null')
        except Exception:
            pass

    init_colors()

    state = {
        'running':  True,
        'messages': ['[COS] Welcome to Channel Operating System v1.0',
                     '[COS] Click a menu item or press its letter key.'],
    }

    mouse_pos  = (0, 0)
    active_key = None

    # Pre-compute menubar col positions (rough, recomputed in loop)
    menu_col_positions = {}

    while state['running']:
        H, W = stdscr.getmaxyx()
        draw_desktop(stdscr, H, W)
        positions = draw_menubar(stdscr, W, active_key)
        draw_messages(stdscr, H, W, state['messages'])
        draw_statusbar(stdscr, H, W, mouse_pos,
                       'Click menu items or press letter keys')
        draw_cursor_dot(stdscr, H, W, *mouse_pos)
        stdscr.refresh()

        stdscr.timeout(250)
        key = stdscr.getch()

        if key == -1:
            continue

        # ── Keyboard shortcuts ──
        if key == ord('q') or key == 27:
            state['running'] = False
            continue

        if chr(key).lower() in MENUS:
            k = chr(key).lower()
            # find column for that menu key
            col = positions.get(k, 0)
            action = Dropdown(stdscr, k, col).run()
            if action:
                handle_action(action, stdscr, state)
            continue

        # ── Mouse events ──
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                mouse_pos = (mx, my)

                # Click on menubar (row 0)?
                if my == 0 and bstate & (curses.BUTTON1_PRESSED |
                                          curses.BUTTON1_CLICKED):
                    clicked_menu = None
                    for k, col in positions.items():
                        label = f' {MENUS[k]["label"]} [{MENUS[k]["key"]}] '
                        if col <= mx < col + len(label):
                            clicked_menu = k
                            break
                    if clicked_menu:
                        action = Dropdown(stdscr, clicked_menu,
                                          positions[clicked_menu]).run()
                        if action:
                            handle_action(action, stdscr, state)

            except curses.error:
                pass

        # ── Function keys ──
        elif key == curses.KEY_F1:
            handle_action('help', stdscr, state)
        elif key == curses.KEY_RESIZE:
            curses.resizeterm(*stdscr.getmaxyx())

    # Restore terminal mouse
    print('\033[?1003l', end='', flush=True)


def run():
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    finally:
        # Ensure mouse tracking is disabled on exit
        print('\033[?1003l', end='', flush=True)
        print('\nCOS exited. Channel closed.')

if __name__ == '__main__':
    run()
