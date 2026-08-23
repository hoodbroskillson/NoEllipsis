# VHS tape for an animated demo. Requires https://github.com/charmbracelet/vhs
# This repository ships a static snapshot (docs/demo.svg) generated from the
# same real CLI commands — not a fabricated GIF.

Output docs/demo.gif

Set Shell bash
Set FontSize 14
Set Width 980
Set Height 520
Set Theme "Catppuccin Mocha"
Set PlaybackSpeed 0.8

Type "noellipsis check examples/ok_examples.py --format text"
Enter
Sleep 1s
Type "noellipsis check examples/incomplete.py --format text"
Enter
Sleep 1s
Type "noellipsis compare examples/generated_snippet.py --against examples/original_module.py --format text"
Enter
Sleep 2s
