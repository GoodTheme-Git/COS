TCF IBBS for COS Neptune
========================

The TCF Internal Bulletin Board System, as a native Aero window.

What you get
  * IBBS in the APPS menu, the Start menu and on the desktop.
  * Rooms on the left, live chat in the middle. Type and press Enter.
    /name NEW changes your name, /room NAME switches rooms.
  * Files: share a file to the board, download files others shared
    (into home/Downloads, sha256 checked).
  * A notification balloon when someone posts while IBBS is in the background.

Local board or board server
  With no server set, IBBS uses a board folder on this machine
  (~/.tcf_ibbs, the same one ibbs.py uses), so it talks to anyone on this
  computer running ibbs.py or COS v2.4's IBBS window.

  To talk across machines, run  python3 ibbs.py --serve  on one of them, then
  open IBBS > Settings here and enter that machine as host:port (port 8619 by
  default), plus the IBBS_TOKEN if the board has one.

Under the hood
  The package carries ibbs.py v1.4.0 itself, and the window imports it, the
  same way COS v2.4's built-in IBBS does. Settings are kept in
  home/.neptune/ibbs.json.

This package needs COS 3.0 (Neptune). COS v2.4 already has IBBS built in.
