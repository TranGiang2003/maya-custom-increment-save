# Maya Custom Increment and Save

Choose how Maya numbers your scene versions: `file.ma` → `file_001.ma` → `file_002.ma`.

[Download the latest release](https://github.com/TranGiang2003/maya-custom-increment-save/releases/latest).

## Install

1. Download **CustomIncrementSave-1.0.1.zip** from Releases and extract the entire ZIP.
2. Open Maya and drag **install_custom_increment_save_1_0_1.py** onto the viewport.
3. Click the little option box beside **File > Increment and Save** to customize your filenames.

Keep the extracted installer, `scripts`, and `plug-ins` folders together during installation. The installer loads the plug-in and enables **Auto load**. To update, extract the new ZIP into a fresh folder and drag its installer onto the viewport again.

## Use

Choose a separator (`_`, `.`, or `-`), number of digits, and starting version. The preview shows the next available filename. Click **Save Settings**, then use Maya's usual **Increment and Save** command or shortcut.

Existing versions continue from their current number: `file.0007.ma` becomes `file_008.ma` with the default settings. A final separator followed by digits counts as a version suffix. Existing filenames are skipped, and scenes keep their folder and `.ma` or `.mb` format.

## Turn on or off

Open **Windows > Settings/Preferences > Plug-in Manager** and find **customIncrementSavePlugin.py**.

- **Loaded** turns the tool on. Uncheck it to restore Maya's original Increment and Save.
- **Auto load** enables it when Maya starts.

## Compatibility and license

Requires Maya 2023 or newer with Python 3. Tested on **Maya 2023.3 for Windows**; other versions and operating systems are unverified.

Released under the [MIT license](LICENSE). Developed with assistance from OpenAI ChatGPT/Codex.

Independent project; Autodesk and Maya are trademarks of Autodesk, Inc.
