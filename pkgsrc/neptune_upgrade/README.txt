Upgrade to COS 3.0 "Neptune"
============================

This package upgrades a COS v2.4 machine to COS Neptune, side by side:

  * COS v2.4 stays installed and keeps working, unchanged.
  * Neptune is copied to ~/cos/neptune (or ~/neptune if there is no ~/cos).
  * Your settings come along: IBBS board, sound on/off, wallpaper picture,
    web bookmarks. Your COS 2.x programs in ~/.cos/apps already run in
    Neptune's compatibility mode, nothing to move.
  * "COS Neptune" appears in the v2.4 APPS menu and on the desktop.

After installing, open APPS > Upgrade to COS Neptune and follow the four
steps. The Upgrade Advisor checks this computer first and tells you how to
install anything missing (Neptune needs Python 3.8+, Pillow and numpy).

Running it again later updates Neptune's program files (the old ones are kept
in backup/) and never touches Neptune's home folder.

Not carried over: the v2.4 login password (Neptune's lock screen uses its own;
set one in Neptune under CONTROL > Lock Screen).
