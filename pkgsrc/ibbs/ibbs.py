#!/usr/bin/env python3
"""TCF Internal Bulletin Board System (TCF_IBBS).

Communication software for both carbon-based humans and silicon-based humans.

Messages live in a board directory (one file per room). On one machine,
everyone pointing at the same directory can talk to each other.
Set IBBS_DIR to change where the board lives (default: ~/.tcf_ibbs).

Across machines, one machine runs `ibbs.py --serve` and the others set
IBBS_SERVER=<host>:<port> (or pass --server=) to use that machine's board.
Set the same IBBS_TOKEN everywhere to keep strangers off the board.
"""

import contextlib
import fcntl
import getpass
import hashlib
import json
import os
import re
import shutil
import socket
import uuid
import sys
import textwrap
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.4.0"
DEFAULT_ROOM = "general"
DEFAULT_PORT = 8619
BOARD_DIR = os.path.expanduser(os.environ.get("IBBS_DIR", "~/.tcf_ibbs"))
SERVER = os.environ.get("IBBS_SERVER", "")
TOKEN = os.environ.get("IBBS_TOKEN", "")
POLL_SECONDS = 0.5
MAX_FILE_MB = int(os.environ.get("IBBS_MAX_FILE_MB", "256"))
CHUNK = 1 << 16
SELF_PATH = os.path.realpath(__file__)
LATEST_SEEN = None  # newest version the board server has advertised to us
HOST = socket.gethostname().split(".")[0]
CLIENT_ID = uuid.uuid4().hex[:12]  # tells this running copy apart from every other one

HELP = f"""\
=============================================
TCF Internal Bulletin Board System (TCF_IBBS) v{VERSION}
=============================================
Welcome to the TCF_IBBS! The TCF_IBBS is a communication software for both
carbon-based humans and silicon-based humans.

======
SYNTAX
======
shell (easiest for carbon-humans):
    python3 ibbs.py
command line args (best for silicon-based humans):
    python3 ibbs.py --room=<ROOM> "<message>"

========
CMD Args
========
--room=<ROOM>     -r=<ROOM>   | What room to use. (Rooms are chat sections.)
--monitor --reciving -R       | Receive messages instead of sending them.
--send=<MESSAGE>  -s=<MESSAGE>| Send a message of your choosing.
--chat            -c          | Send and receive in a minimal chat environment.
--name=<NAME>     -n=<NAME>   | Who you are (default: $IBBS_NAME or user@machine).
--last=<N>        -l=<N>      | With --monitor: how many old messages to show (default 20).
--once            -o          | With --monitor: print messages and exit instead of following.
--splitscreen     -S          | Chat in a split screen: incoming on the left, you on the right.
--rooms                       | List the rooms that exist.
--put=<PATH>                  | Upload a file to the board and announce it in --room.
--get=<NAME>                  | Download a board file (checks its sha256). --out=<DIR> picks where.
--files                       | List the files on the board.
--update          -u          | Download the newest ibbs.py from the board server.
--force                       | With --update: reinstall even if not newer. With --get: overwrite.
--serve                       | Host the board for other machines (Ctrl+C to stop).
--port=<PORT>     -p=<PORT>   | With --serve: port to listen on (default {DEFAULT_PORT}).
--server=<HOST:PORT>          | Use the board hosted on another machine ($IBBS_SERVER).
--token=<SECRET>              | Shared password for --serve/--server ($IBBS_TOKEN).
--version         -v          | Tells you the current IBBS version.
--help            -h          | Shows this help menu.

Board directory: {BOARD_DIR}  (change it with the IBBS_DIR environment variable)
Board server:    {SERVER or "(none - using the local board)"}

=========
MORE INFO
=========
Github  - GoodTheme-Git/tcf_ibbs
Youtube - Good Theme Studios or @goodthemestudiosreal
E-mail  - meonyourtub@gmail.com
================================================="""

SHELL_HELP = """\
Commands:
  /room <ROOM>   switch rooms            /rooms        list rooms
  /read [N]      show the last N messages (default 20)
  /chat          live chat in this room  /name <NAME>  change your name
  /help          this list               /quit         leave
Anything that doesn't start with / is sent as a message."""

TCF_ART = r"""
 _____  ___  ___
|_   _|/ __|| __|
  | | | (__ | _|
  |_|  \___||_|
""".strip("\n").splitlines()


# ---------------------------------------------------------------- storage

def clean_room(room):
    room = re.sub(r"[^A-Za-z0-9_-]+", "-", room.strip()).strip("-").lower()
    if not room:
        raise ValueError("room names need at least one letter or number")
    return room


def room_path(room):
    return os.path.join(BOARD_DIR, clean_room(room) + ".jsonl")


def list_rooms():
    if SERVER:
        return remote("GET", "/rooms")["rooms"]
    if not os.path.isdir(BOARD_DIR):
        return []
    return sorted(f[:-6] for f in os.listdir(BOARD_DIR) if f.endswith(".jsonl"))


def post(room, author, text, host=None, client=None):
    host, client = host or HOST, client or CLIENT_ID
    if SERVER:
        return remote("POST", f"/room/{clean_room(room)}",
                      {"from": author, "text": text, "host": host, "client": client})
    os.makedirs(BOARD_DIR, exist_ok=True)
    msg = {"time": time.time(), "from": author, "text": text, "host": host, "client": client}
    with open(room_path(room), "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(msg) + "\n")
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return msg


def parse_lines(lines):
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # skip a damaged line instead of crashing
    return out


def read_all(room):
    if SERVER:
        return follow(room, 0)[0]
    try:
        with open(room_path(room), encoding="utf-8") as f:
            return parse_lines(f)
    except FileNotFoundError:
        return []


def follow(room, offset):
    """Return (new messages, new offset) for anything written after offset."""
    if SERVER:
        got = remote("GET", f"/room/{clean_room(room)}?since={offset}")
        return got["messages"], got["offset"]
    try:
        with open(room_path(room), encoding="utf-8") as f:
            f.seek(offset)
            data = f.read()
    except FileNotFoundError:
        return [], 0
    complete = data.rsplit("\n", 1)[0] + "\n" if "\n" in data else ""
    return parse_lines(complete.splitlines()), offset + len(complete.encode("utf-8"))


def remote(method, path, body=None, raw=None, length=None, stream=False):
    """Talk to the board server. raw+length uploads a file object; stream=True returns
    the open response instead of parsed JSON (caller closes it)."""
    url = ("" if "://" in SERVER else "http://") + SERVER.rstrip("/") + path
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    if raw is not None:
        req.add_header("Content-Type", "application/octet-stream")
        req.add_header("Content-Length", str(length))
    else:
        req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("X-IBBS-Token", TOKEN)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        note_server_version(resp.headers.get("X-IBBS-Version"))
        if stream:
            return resp
        with resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise ConnectionError(f"board server said {e.code}: {e.read().decode(errors='replace')}")
    except (urllib.error.URLError, OSError) as e:
        raise ConnectionError(f"can't reach board server {SERVER}: {getattr(e, 'reason', e)}")


class BoardHandler(BaseHTTPRequestHandler):
    server_version = f"TCF_IBBS/{VERSION}"

    def reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-IBBS-Version", file_version(read_self()) or VERSION)
        self.end_headers()
        self.wfile.write(body)

    def route(self):
        if TOKEN and self.headers.get("X-IBBS-Token") != TOKEN:
            self.reply(403, {"error": "wrong or missing token"})
            return None
        url = urllib.parse.urlsplit(self.path)
        parts = url.path.strip("/").split("/")
        return parts, urllib.parse.parse_qs(url.query)

    def do_GET(self):
        routed = self.route()
        if not routed:
            return
        parts, query = routed
        try:
            if parts == ["rooms"]:
                self.reply(200, {"rooms": list_rooms()})
            elif parts == ["ibbs.py"]:
                code = read_self()
                self.reply(200, {"version": file_version(code), "code": code})
            elif parts == ["files"]:
                self.reply(200, {"files": list_files()})
            elif parts == ["limits"]:
                self.reply(200, {"max_file_mb": MAX_FILE_MB})
            elif len(parts) == 2 and parts[0] == "file":
                self.send_file(urllib.parse.unquote(parts[1]))
            elif len(parts) == 2 and parts[0] == "room":
                since = query.get("since", ["0"])[0]
                if since == "end":
                    self.reply(200, {"messages": [], "offset": end_offset(parts[1])})
                else:
                    msgs, offset = follow(parts[1], max(0, int(since)))
                    self.reply(200, {"messages": msgs, "offset": offset})
            else:
                self.reply(404, {"error": "no such endpoint"})
        except ValueError as e:
            self.reply(400, {"error": str(e)})

    def do_POST(self):
        routed = self.route()
        if not routed:
            return
        parts, query = routed
        if len(parts) == 2 and parts[0] == "file":
            self.take_file(urllib.parse.unquote(parts[1]), query)
            return
        if len(parts) != 2 or parts[0] != "room":
            self.reply(404, {"error": "no such endpoint"})
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            text = str(body["text"]).strip()
            if not text:
                raise ValueError("empty message")
            self.reply(200, post(parts[1], str(body.get("from") or "anonymous"), text,
                                 str(body.get("host") or "?"), str(body.get("client") or "?")))
        except (ValueError, KeyError, TypeError) as e:
            self.reply(400, {"error": f"bad message: {e}"})

    def send_file(self, name):
        try:
            path, info = file_info(name)
            f = open(path, "rb")
        except FileNotFoundError:
            self.reply(404, {"error": f"no file called {name!r} on this board"})
            return
        with f:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(os.fstat(f.fileno()).st_size))
            self.send_header("X-IBBS-SHA256", info["sha256"])
            self.send_header("X-IBBS-Version", file_version(read_self()) or VERSION)
            self.end_headers()
            shutil.copyfileobj(f, self.wfile, CHUNK)

    def take_file(self, name, query):
        arg = lambda key, default: query.get(key, [default])[0]
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.reply(411, {"error": "uploads need a Content-Length"})
            return
        if length > MAX_FILE_MB * 1024 * 1024:
            self.close_connection = True  # don't read the body we're refusing
            self.reply(413, {"error": f"file is over this board's {MAX_FILE_MB}MB limit"})
            return
        try:
            self.reply(200, store_file(name, self.rfile, length, arg("from", "anonymous"),
                                       arg("host", "?"), arg("client", "?"), arg("room", DEFAULT_ROOM)))
        except ValueError as e:
            self.close_connection = True
            self.reply(400, {"error": str(e)})

    def log_message(self, fmt_, *args):
        pass  # keep the server terminal quiet


def read_self():
    # read fresh each time, so editing ibbs.py on the host publishes it right away
    with open(SELF_PATH, encoding="utf-8") as f:
        return f.read()


def file_version(code):
    m = re.search(r'^VERSION = "([^"]+)"', code, re.M)
    return m.group(1) if m else None


def version_tuple(v):
    return tuple(int(n) for n in re.findall(r"\d+", v or ""))


def note_server_version(v):
    global LATEST_SEEN
    if v and version_tuple(v) > version_tuple(LATEST_SEEN or VERSION):
        LATEST_SEEN = v


def update(force):
    if not SERVER:
        raise SystemExit("ibbs: --update needs a board server (set IBBS_SERVER or --server=)")
    got = remote("GET", "/ibbs.py")
    new, code = got.get("version"), got.get("code", "")
    if not new or not code:
        raise SystemExit("ibbs: the server sent back something that isn't ibbs.py")
    if version_tuple(new) <= version_tuple(VERSION) and not force:
        print(f"already up to date (you have v{VERSION}, server has v{new})")
        return
    try:
        compile(code, "ibbs.py", "exec")
    except SyntaxError as e:
        raise SystemExit(f"ibbs: server's ibbs.py v{new} is broken ({e}), not installing it")
    old_dir = os.path.join(BOARD_DIR, "old")
    os.makedirs(old_dir, exist_ok=True)
    backup = os.path.join(old_dir, f"ibbs-{VERSION}-{int(time.time())}.py")
    shutil.copy2(SELF_PATH, backup)
    tmp = SELF_PATH + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(code)
    shutil.copymode(SELF_PATH, tmp)
    os.replace(tmp, SELF_PATH)
    print(f"updated v{VERSION} -> v{new}  (old copy saved at {backup})")


def serve(port):
    httpd = ThreadingHTTPServer(("0.0.0.0", port), BoardHandler)
    print(f"TCF_IBBS v{VERSION} serving {BOARD_DIR} on port {port}")
    print(f"other machines: IBBS_SERVER=<this machine's name or IP>:{port}")
    sys.stdout.flush()
    if not TOKEN:
        print("warning: no IBBS_TOKEN set - anyone on your network can read and post", flush=True)
    httpd.serve_forever()


def end_offset(room):
    if SERVER:
        return remote("GET", f"/room/{clean_room(room)}?since=end")["offset"]
    try:
        return os.path.getsize(room_path(room))
    except FileNotFoundError:
        return 0


def is_mine(msg, author):
    """Sent by this running copy, or by this name on this machine in an earlier session."""
    if msg.get("client") == CLIENT_ID:
        return True
    return msg.get("from") == author and msg.get("host") == HOST


def rename(text, author):
    """Handle '/name NEW' typed into chat; returns the (maybe new) name, or None if not /name."""
    cmd, _, arg = text.partition(" ")
    if cmd != "/name":
        return None
    return arg.strip() or author


def fmt(msg):
    stamp = datetime.fromtimestamp(msg.get("time", 0)).strftime("%Y-%m-%d %H:%M:%S")
    return f"[{stamp}] <{msg.get('from', '?')}> {msg.get('text', '')}"


def configure(board_dir=None, server=None, token=None):
    """Point this module at a board after import (for programs that embed ibbs, like COS)."""
    global BOARD_DIR, SERVER, TOKEN
    if board_dir is not None:
        BOARD_DIR = os.path.expanduser(board_dir)
    if server is not None:
        SERVER = server
    if token is not None:
        TOKEN = token


# ---------------------------------------------------------------- files
# Stored in BOARD_DIR/files/<name>, with the size/sha256 beside it in .<name>.json.
# Cleaned names never start with a dot, so the sidecars can't collide with real files.

def clean_filename(name):
    name = os.path.basename(name.replace("\\", "/")).strip()
    name = re.sub(r"[^A-Za-z0-9._()+ -]+", "_", name).lstrip(".")
    if not name:
        raise ValueError("that isn't a usable file name")
    return name[:200]


def files_dir():
    return os.path.join(BOARD_DIR, "files")


def human_size(n):
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def file_info(name):
    """Return (path, info) for a stored file; FileNotFoundError if there isn't one."""
    name = clean_filename(name)
    with open(os.path.join(files_dir(), f".{name}.json"), encoding="utf-8") as m:
        return os.path.join(files_dir(), name), json.load(m)


def list_files():
    if SERVER:
        return remote("GET", "/files")["files"]
    out = []
    if os.path.isdir(files_dir()):
        for f in sorted(os.listdir(files_dir())):
            if not f.startswith("."):
                with contextlib.suppress(FileNotFoundError, json.JSONDecodeError):
                    out.append(file_info(f)[1])
    return out


def store_file(name, stream, length, author, host, client, room):
    """Copy length bytes from stream into the board's files, announce it in room."""
    name = clean_filename(name)
    if length > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"file is over this board's {MAX_FILE_MB}MB limit")
    os.makedirs(files_dir(), exist_ok=True)
    tmp = os.path.join(files_dir(), f".{name}.part-{uuid.uuid4().hex[:8]}")
    digest, left = hashlib.sha256(), length
    try:
        with open(tmp, "wb") as f:
            while left > 0:
                chunk = stream.read(min(CHUNK, left))
                if not chunk:
                    raise ValueError("the upload ended early")
                digest.update(chunk)
                f.write(chunk)
                left -= len(chunk)
        os.replace(tmp, os.path.join(files_dir(), name))
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.remove(tmp)
        raise
    info = {"name": name, "size": length, "sha256": digest.hexdigest(),
            "time": time.time(), "from": author}
    with open(os.path.join(files_dir(), f".{name}.json"), "w", encoding="utf-8") as m:
        json.dump(info, m)
    post(room, author, f"[file] {name}  {human_size(length)}  sha256 {info['sha256']}"
                       f"  - get it with: ibbs.py --get=\"{name}\"", host, client)
    return info


def put_file(path, room, author):
    name = clean_filename(os.path.basename(path))
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if not SERVER:
            return store_file(name, f, size, author, HOST, CLIENT_ID, room)
        # ask first: a refused upload otherwise just looks like a broken pipe
        with contextlib.suppress(ConnectionError):  # servers before v1.4 have no /limits
            limit = remote("GET", "/limits")["max_file_mb"]
            if size > limit * 1024 * 1024:
                raise ValueError(f"{name} is {human_size(size)}, over the board's {limit}MB limit")
        query = urllib.parse.urlencode({"room": room, "from": author, "host": HOST, "client": CLIENT_ID})
        return remote("POST", f"/file/{urllib.parse.quote(name)}?{query}", raw=f, length=size)


def get_file(name, out_dir, force):
    """Download a board file into out_dir, refusing to keep it if the sha256 doesn't match."""
    name = clean_filename(name)
    dest = os.path.join(os.path.expanduser(out_dir), name)
    if os.path.exists(dest) and not force:
        raise FileExistsError(f"{dest} already exists (add --force to overwrite it)")
    if SERVER:
        src = remote("GET", f"/file/{urllib.parse.quote(name)}", stream=True)
        expected = src.headers.get("X-IBBS-SHA256", "")
    else:
        try:
            path, info = file_info(name)
            src, expected = open(path, "rb"), info["sha256"]
        except FileNotFoundError:
            raise FileNotFoundError(f"no file called {name!r} on this board") from None
    tmp, digest, size = dest + ".part", hashlib.sha256(), 0
    with src, open(tmp, "wb") as f:
        while chunk := src.read(CHUNK):
            digest.update(chunk)
            f.write(chunk)
            size += len(chunk)
    if digest.hexdigest() != expected:
        os.remove(tmp)
        raise ValueError(f"{name} came through damaged (sha256 mismatch) - nothing saved, try again")
    os.replace(tmp, dest)
    return dest, size, expected


# ---------------------------------------------------------------- modes

def show_last(room, n):
    msgs = read_all(room)
    if not msgs:
        print(f"(no messages in #{clean_room(room)} yet)")
    for m in msgs[-n:] if n > 0 else []:
        print(fmt(m))


def monitor(room, last, once):
    offset = end_offset(room)
    show_last(room, last)
    if once:
        return
    print(f"-- watching #{clean_room(room)} (Ctrl+C to stop) --")
    while True:
        time.sleep(POLL_SECONDS)
        try:
            msgs, offset = follow(room, offset)
        except ConnectionError as e:
            print(f"({e} - retrying)", file=sys.stderr, flush=True)
            time.sleep(5)
            continue
        for m in msgs:
            print(fmt(m), flush=True)


def chat(room, author):
    print(f"-- chatting in #{clean_room(room)} as {author}. Type /quit to leave. --")
    show_last(room, 10)
    offset = [end_offset(room)]
    stop = threading.Event()

    def receiver():
        while not stop.is_set():
            try:
                msgs, offset[0] = follow(room, offset[0])
            except ConnectionError:
                stop.wait(5)
                continue
            for m in msgs:
                if m.get("client") != CLIENT_ID:
                    print("\r" + fmt(m) + "\n> ", end="", flush=True)
            stop.wait(POLL_SECONDS)

    threading.Thread(target=receiver, daemon=True).start()
    try:
        while True:
            text = input("> ").strip()
            if text in ("/quit", "/exit", "/q"):
                break
            new = rename(text, author)
            if new:
                author = new
                print(f"(you are now {author})")
            elif text:
                post(room, author, text)
    except EOFError:
        pass
    finally:
        stop.set()
    return author


class SplitScreen:
    """Amber-on-black chat: incoming messages type themselves out on the left,
    your side (what you've said, and what you're typing) on the right."""

    def __init__(self, scr, room, author, inbox):
        import curses
        self.c, self.scr, self.room, self.author, self.inbox = curses, scr, room, author, inbox
        self.left = [f"TCF_IBBS v{VERSION}  //  #{room}  //  {author}", ""]
        self.done, self.chars = 0, 0  # entries fully typed, chars typed of the next one
        self.mine, self.buf, self.status = [], "", ""
        curses.curs_set(0)
        scr.timeout(30)
        if curses.has_colors():
            curses.start_color()
            amber = 214 if curses.COLORS >= 256 else curses.COLOR_YELLOW
            curses.init_pair(1, amber, curses.COLOR_BLACK)
            scr.bkgd(" ", curses.color_pair(1))

    def put(self, y, x, text):
        try:
            self.scr.addstr(y, x, text)
        except self.c.error:
            pass  # writing the bottom-right cell always "fails"; ignore it

    def box(self, y, x, h, w):
        self.put(y, x, "-" * w)
        self.put(y + h - 1, x, "-" * w)
        for row in range(y + 1, y + h - 1):
            self.put(row, x, "|")
            self.put(row, x + w - 1, "|")

    @staticmethod
    def wrap(text, width):
        return textwrap.wrap(text, max(width, 1), subsequent_indent="  ",
                             drop_whitespace=False) or [""]

    def tick(self):
        if self.done < len(self.left):
            backlog = len(self.left) - self.done
            self.chars += 1 + backlog * 2  # speed up when lots is waiting
            if self.chars >= len(self.left[self.done]):
                self.done, self.chars = self.done + 1, 0

    def draw(self):
        h, w = self.scr.getmaxyx()
        self.scr.erase()
        if w < 50 or h < 14:
            self.put(0, 0, "make the window bigger (50x14+)")
            self.scr.refresh()
            return
        lw = w * 3 // 5
        rx, rw = lw + 1, w - lw - 1
        art_h = len(TCF_ART) + 4
        top_h = h - art_h

        # left: incoming, typewriter style
        self.box(0, 0, h, lw)
        inner = lw - 4
        lines = []
        for entry in self.left[:self.done]:
            lines += self.wrap(entry, inner)
        if self.done < len(self.left):
            left_to_show = self.chars
            for part in self.wrap(self.left[self.done], inner):
                lines.append(part[:left_to_show])
                left_to_show -= len(part)
                if left_to_show <= 0:
                    break
        lines = lines[-(h - 2):]
        for i, line in enumerate(lines):
            self.put(1 + i, 2, line)
        if int(time.time() * 2) % 2 and lines:
            self.put(len(lines), 2 + len(lines[-1]), "_")

        # right top: you
        self.box(0, rx, top_h, rw)
        self.put(0, rx + 2, f" you > #{self.room} ")
        inner = rw - 4
        mine = []
        for entry in self.mine:
            mine += self.wrap(entry, inner)
        mine = mine[-max(top_h - 4, 0):]
        for i, line in enumerate(mine):
            self.put(1 + i, rx + 2, line)
        self.put(top_h - 3, rx + 1, "-" * (rw - 2))
        shown = ("> " + self.buf)[-(inner - 1):]
        self.put(top_h - 2, rx + 2, shown + ("_" if int(time.time() * 2) % 2 else " "))

        # right bottom: art and status
        self.box(top_h, rx, art_h, rw)
        for i, line in enumerate(TCF_ART):
            self.put(top_h + 1 + i, rx + max((rw - len(line)) // 2, 1), line[:rw - 2])
        status = self.status or (f"server {SERVER}" if SERVER else "local board")
        if LATEST_SEEN:
            status = f"v{LATEST_SEEN} available: --update"
        self.put(top_h + art_h - 2, rx + 2, status[:rw - 4])
        self.scr.refresh()

    def take(self, m):
        stamp = datetime.fromtimestamp(m.get("time", 0)).strftime("%H:%M")
        if is_mine(m, self.author):
            self.mine.append(f"{stamp} {m.get('text', '')}")
        else:
            self.left.append(f"{stamp} {m.get('from', '?')}: {m.get('text', '')}")

    def run(self):
        import queue
        while True:
            try:
                while True:
                    item = self.inbox.get_nowait()
                    if isinstance(item, str):
                        self.status = item  # receiver reporting trouble ("" = fine)
                    else:
                        self.take(item)
            except queue.Empty:
                pass
            self.tick()
            self.draw()
            try:
                key = self.scr.get_wch()
            except self.c.error:
                continue  # no key pressed this tick
            if key in ("\n", "\r", self.c.KEY_ENTER):
                text, self.buf = self.buf.strip(), ""
                if text in ("/quit", "/exit", "/q"):
                    return
                new = rename(text, self.author)
                if new:
                    self.author = new
                    self.mine.append(f"(you are now {new})")
                elif text:
                    try:
                        post(self.room, self.author, text)
                    except ConnectionError as e:
                        self.status = str(e)
            elif key in ("\x7f", "\b", self.c.KEY_BACKSPACE):
                self.buf = self.buf[:-1]
            elif key == "\x1b":
                return
            elif isinstance(key, str) and key.isprintable():
                self.buf += key


def splitscreen(room, author):
    import curses
    import locale
    import queue
    locale.setlocale(locale.LC_ALL, "")  # without this curses mangles non-ASCII text
    history, offset = follow(room, 0)
    inbox = queue.Queue()
    for m in history[-20:]:
        inbox.put(m)
    stop = threading.Event()

    def receiver():
        nonlocal offset
        while not stop.is_set():
            try:
                msgs, offset = follow(room, offset)
                inbox.put("")
            except ConnectionError as e:
                inbox.put(f"{e} - retrying")
                stop.wait(5)
                continue
            for m in msgs:
                inbox.put(m)
            stop.wait(POLL_SECONDS)

    threading.Thread(target=receiver, daemon=True).start()
    os.environ.setdefault("ESCDELAY", "25")  # make Esc quit right away
    try:
        curses.wrapper(lambda scr: SplitScreen(scr, room, author, inbox).run())
    finally:
        stop.set()


def shell(room, author):
    print(f"TCF_IBBS v{VERSION} - you are {author}, in #{room}")
    print(SHELL_HELP)
    while True:
        try:
            line = input(f"[#{room}] ").strip()
        except EOFError:
            print()
            return
        if not line:
            continue
        if not line.startswith("/"):
            post(room, author, line)
            print("(sent)")
            continue
        cmd, _, arg = line.partition(" ")
        arg = arg.strip()
        if cmd in ("/quit", "/exit", "/q"):
            return
        elif cmd == "/help":
            print(SHELL_HELP)
        elif cmd == "/room" and arg:
            try:
                room = clean_room(arg)
            except ValueError as e:
                print(f"error: {e}")
        elif cmd == "/rooms":
            print(", ".join(list_rooms()) or "(no rooms yet)")
        elif cmd == "/read":
            show_last(room, int(arg) if arg.isdigit() else 20)
        elif cmd == "/chat":
            author = chat(room, author)
        elif cmd == "/name" and arg:
            author = arg
            print(f"(you are now {author})")
        else:
            print("unknown command - type /help")


# ---------------------------------------------------------------- args

FLAGS = {
    "--room": "room", "-r": "room",
    "--send": "send", "-s": "send",
    "--name": "name", "-n": "name",
    "--last": "last", "-l": "last",
    "--monitor": "monitor", "--reciving": "monitor", "--receiving": "monitor", "-R": "monitor",
    "--chat": "chat", "-c": "chat",
    "--once": "once", "-o": "once",
    "--rooms": "rooms",
    "--splitscreen": "split", "-S": "split",
    "--update": "update", "-u": "update",
    "--force": "force",
    "--put": "put",
    "--get": "get",
    "--out": "out",
    "--files": "files",
    "--serve": "serve",
    "--port": "port", "-p": "port",
    "--server": "server",
    "--token": "token",
    "--version": "version", "-v": "version",
    "--help": "help", "-h": "help",
}
TAKES_VALUE = {"room", "send", "name", "last", "port", "server", "token", "put", "get", "out"}


def parse_args(argv):
    opts, words = {}, []
    i = 0
    while i < len(argv):
        arg = argv[i]
        flag, eq, value = arg.partition("=")
        if flag not in FLAGS:
            if arg.startswith("-") and len(arg) > 1:
                raise SystemExit(f"ibbs: unknown option {arg!r} (try --help)")
            words.append(arg)
        elif FLAGS[flag] in TAKES_VALUE:
            if not eq:  # allow "--room general" as well as "--room=general"
                i += 1
                if i >= len(argv):
                    raise SystemExit(f"ibbs: {flag} needs a value")
                value = argv[i]
            opts[FLAGS[flag]] = value
        else:
            opts[FLAGS[flag]] = True
        i += 1
    return opts, words


def main(argv):
    global SERVER, TOKEN
    opts, words = parse_args(argv)
    SERVER = opts.get("server", SERVER)
    TOKEN = opts.get("token", TOKEN)
    if opts.get("help"):
        print(HELP)
        return
    if opts.get("version"):
        print(f"TCF_IBBS v{VERSION}")
        return
    if opts.get("update"):
        try:
            update(opts.get("force", False))
        except ConnectionError as e:
            raise SystemExit(f"ibbs: {e}")
        return
    if opts.get("serve"):
        SERVER = ""  # the host always serves its own local board
        port = opts.get("port", str(DEFAULT_PORT))
        if not port.isdigit():
            raise SystemExit(f"ibbs: bad port {port!r}")
        try:
            serve(int(port))
        except KeyboardInterrupt:
            print()
        return

    try:
        room = clean_room(opts.get("room", DEFAULT_ROOM))
    except ValueError as e:
        raise SystemExit(f"ibbs: {e}")
    author = opts.get("name") or os.environ.get("IBBS_NAME") or f"{getpass.getuser()}@{HOST}"
    message = opts.get("send") or " ".join(words)

    try:
        if opts.get("rooms"):
            print("\n".join(list_rooms()) or "(no rooms yet)")
        elif opts.get("files"):
            for f in list_files():
                stamp = datetime.fromtimestamp(f.get("time", 0)).strftime("%Y-%m-%d %H:%M")
                print(f"{f['name']}  {human_size(f['size'])}  {stamp}  from {f.get('from', '?')}"
                      f"  sha256 {f['sha256']}")
        elif opts.get("put"):
            info = put_file(opts["put"], room, author)
            print(f"uploaded {info['name']} ({human_size(info['size'])}, sha256 {info['sha256']})"
                  f" and announced it in #{room}")
        elif opts.get("get"):
            dest, size, sha = get_file(opts["get"], opts.get("out", "."), opts.get("force", False))
            print(f"saved {dest} ({human_size(size)}, sha256 {sha} - verified)")
        elif opts.get("split"):
            splitscreen(room, author)
        elif opts.get("chat"):
            chat(room, author)
        elif opts.get("monitor"):
            last = opts.get("last", "20")
            monitor(room, int(last) if last.isdigit() else 20, opts.get("once", False))
        elif message:
            post(room, author, message)
            print(f"sent to #{room}")
        else:
            shell(room, author)
    except KeyboardInterrupt:
        print()
    except ConnectionError as e:
        raise SystemExit(f"ibbs: {e}")
    except (OSError, ValueError) as e:  # missing/existing files, bad names, damaged downloads
        raise SystemExit(f"ibbs: {e}")
    if LATEST_SEEN:
        print(f"ibbs: v{LATEST_SEEN} is available (you have v{VERSION}) - run: python3 ibbs.py --update",
              file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
