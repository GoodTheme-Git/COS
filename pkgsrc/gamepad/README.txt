COS Gamepad Driver 1.0
======================

Works with any controller Linux reports as a gamepad (Xbox, PlayStation,
Logitech, generic USB pads). Plug it in before COS starts, or press R in
CTRL > Device Manager after plugging it in.

  D-pad          arrow keys (held = repeat)
  A / Cross      Enter
  B / Circle     Esc
  X / Square     left click
  Y / Triangle   Space
  Left stick     move the pointer
  Right bumper   right click
  Left bumper    scroll up
  Start          open the menus (same as Ctrl+F)
  Select / Back  next window (Tab)

COS needs to be able to read /dev/input. If the Device Manager shows
"no permission", run:  python3 cos.py --grant-input
