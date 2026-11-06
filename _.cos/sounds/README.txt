COS sound pack
==============

Drop your own sound files in this folder to replace the
tones COS synthesized for itself. COS looks for each name
below with any of these extensions, in this order:

    .wav  .ogg  .opus  .flac  .mp3

A file you add always wins over the built-in .wav, and COS
never overwrites a file you put here.

Names COS plays:

    boot.wav         COS starts up
    click.wav        a button, menu item or icon is clicked
    close.wav        a window closes
    coin.wav         a sale completes in the POS shell
    drop.wav         a drag is committed, a file is saved
    error.wav        something failed
    key.wav          small keypress tick
    menu.wav         a menu opens / selection moves
    notify.wav       general notification
    open.wav         a window opens
    shutdown.wav     COS exits
    warn.wav         a warning

Short files work best: 50-400 ms for clicks and blips.
Delete a built-in .wav and COS will re-synthesize it on
the next start, or use Preferences > Re-synthesize.
