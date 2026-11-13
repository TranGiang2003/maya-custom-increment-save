"""Custom Increment and Save for Maya 2023+ (Python 3).

Copy to Maya's user scripts folder, then run::

    import custom_increment_save
    custom_increment_save.install()
    custom_increment_save.show_options()
"""

import os
import re
import json
from functools import partial

from maya import cmds, mel, OpenMaya


WINDOW = "customIncrementSaveOptions"
MENU_ITEMS = (
    "customIncrementSaveDivider",
    "customIncrementSaveCommand",
    "customIncrementSaveOptionBox",
)
OPTION_PREFIX = "customIncrementSave_"
DEFAULTS = {"separator": "_", "digits": 3, "start": 1}
SEPARATORS = ("_", ".", "-")
FILE_TYPES = {".ma": "mayaAscii", ".mb": "mayaBinary"}
_saving = False
_original_save_source = globals().get("_original_save_source")
_option_item = globals().get("_option_item")
_refresh_options = None


def _native_save_source():
    """Find Maya's original script even while our MEL wrapper is installed."""
    install_directory = cmds.internalVar(mayaInstallDir=True)
    for subdirectory in ("startup", "others", ""):
        candidate = os.path.join(
            install_directory, "scripts", subdirectory, "incrementAndSaveScene.mel"
        )
        if os.path.isfile(candidate):
            return os.path.abspath(candidate).replace("\\", "/")
    raise RuntimeError(
        "Maya's incrementAndSaveScene.mel is missing from its installation at {}. "
        "The custom save action could not be enabled.".format(install_directory)
    )


def validate_settings(settings):
    """Validate before changing preferences or touching a scene."""
    if settings["separator"] not in SEPARATORS:
        raise ValueError("Choose underscore, dot, or hyphen as the separator.")
    for key, minimum, maximum in (("digits", 1, 12), ("start", 1, 999999999)):
        value = settings[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("{} must be an integer.".format(key))
        if not minimum <= value <= maximum:
            raise ValueError("{} must be between {} and {}.".format(key, minimum, maximum))
    return dict(settings)


def get_settings():
    settings = dict(DEFAULTS)
    for key in settings:
        name = OPTION_PREFIX + key
        if cmds.optionVar(exists=name):
            settings[key] = cmds.optionVar(query=name)
    try:
        return validate_settings(settings)
    except (ValueError, TypeError):
        return dict(DEFAULTS)


def save_settings(settings):
    settings = validate_settings(settings)
    cmds.optionVar(stringValue=(OPTION_PREFIX + "separator", settings["separator"]))
    for key in ("digits", "start"):
        cmds.optionVar(intValue=(OPTION_PREFIX + key, settings[key]))


def next_path(scene_path, settings, exists=os.path.lexists):
    """Return the first free version after this scene's trailing version.

    Trailing _digits, .digits and -digits are recognized at any padding width.
    Earlier numbers in the base name remain intact.
    """
    settings = validate_settings(settings)
    stem, extension = os.path.splitext(os.fspath(scene_path))
    if extension.lower() not in FILE_TYPES:
        raise ValueError("Choose a Maya ASCII (.ma) or Maya Binary (.mb) scene.")
    folder, name = os.path.split(stem)
    match = re.fullmatch(r"(.+)[_.-]([0-9]+)", name)
    number = settings["start"]
    if match:
        name = match.group(1)
        number = int(match.group(2)) + 1
    while True:
        version = str(number).zfill(settings["digits"])
        candidate = os.path.join(folder, name + settings["separator"] + version + extension)
        if not exists(candidate):
            return candidate
        number += 1


def _reserve_path(scene_path, settings):
    """Claim a free name exclusively, including across simultaneous tool saves."""
    while True:
        target = next_path(scene_path, settings)
        try:
            descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
        except FileExistsError:
            continue
        os.close(descriptor)
        return target


def _scene_path():
    if cmds.file(query=True, renameToSave=True):
        return ""
    return cmds.file(query=True, sceneName=True) or ""


def _choose_base_path():
    selection = cmds.fileDialog2(
        caption="Choose a base name for the first version",
        fileMode=0,
        fileFilter="Maya ASCII (*.ma);;Maya Binary (*.mb)",
        returnFilter=True,
        startingDirectory=cmds.workspace(query=True, rootDirectory=True),
        okCaption="Use Base Name",
    )
    if not selection:
        return None
    path = selection[0]
    extension = os.path.splitext(path)[1]
    if not extension:
        chosen_filter = selection[1] if len(selection) > 1 else "Maya ASCII"
        path += ".mb" if "Binary" in chosen_filter else ".ma"
    return path


def increment_and_save(settings=None):
    """Save a new version and return its path. Cancellation returns None.

    Raise on failure so callers can handle errors. The UI wrapper displays them.
    Maya force-saves only the empty file exclusively reserved by this call.
    """
    global _saving
    if _saving:
        raise RuntimeError("Custom Increment and Save is already running.")
    settings = validate_settings(settings if settings is not None else get_settings())
    target = None
    renamed = False
    original_name = OpenMaya.MFileIO.currentFile()
    original_scene_path = _scene_path()
    original_requires_name = not bool(original_scene_path)
    _saving = True
    try:
        base = original_scene_path or _choose_base_path()
        if base is None:
            return None
        target = _reserve_path(base, settings)
        scene_type = FILE_TYPES[os.path.splitext(base)[1].lower()]
        renamed = True
        cmds.file(rename=target)
        result = cmds.file(save=True, type=scene_type, force=True)
        if not result or not os.path.isfile(target) or os.path.getsize(target) == 0:
            raise RuntimeError("Maya did not produce a complete scene file.")
        print("Custom Increment and Save saved {}".format(target))
        return target
    except Exception as error:
        if renamed:
            # Restore the file identity without opening/newing the scene or losing edits.
            OpenMaya.MFileIO.setCurrentFile(original_name)
            cmds.file(renameToSave=original_requires_name)
            cmds.file(modified=True)
        detail = ""
        if target and os.path.exists(target):
            if os.path.getsize(target) == 0:
                os.unlink(target)
            else:
                detail = " A recovery file may remain at {}.".format(target)
        raise RuntimeError("Could not increment and save {}. {}{}".format(
            target or "the scene", error, detail
        )) from error
    finally:
        _saving = False
        if _refresh_options is not None:
            _refresh_options()


def _run_from_ui(*args, **kwargs):
    try:
        return increment_and_save(**kwargs)
    except Exception as error:
        cmds.warning(str(error))
        cmds.confirmDialog(
            title="Increment and Save failed", message=str(error),
            button=["OK"], defaultButton="OK",
        )
        return None


def show_options(*args):
    """Open the settings window with a preview of the next available filename."""
    global _refresh_options
    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)
    settings = get_settings()
    window = cmds.window(WINDOW, title="Custom Increment and Save", widthHeight=(560, 310))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnOffset=("both", 14))
    cmds.separator(height=6, style="none")
    separator = cmds.optionMenuGrp(label="Version separator")
    for value, label in (("_", "Underscore (_)"), (".", "Dot (.)"), ("-", "Hyphen (-)")):
        cmds.menuItem(label=label)
    cmds.optionMenuGrp(separator, edit=True, select=SEPARATORS.index(settings["separator"]) + 1)
    digits = cmds.intFieldGrp(label="Number of digits", value1=settings["digits"])
    start = cmds.intFieldGrp(label="Starting version", value1=settings["start"])
    cmds.text(label="Next save", align="left")
    preview = cmds.textField(editable=False)
    status = cmds.text(label="", align="left", wordWrap=True, height=32)
    cmds.text(
        label="A trailing _number, .number, or -number is treated as the version.\n"
              "Starting version applies when the name has no version suffix.",
        align="left", wordWrap=True, height=34,
    )

    def read_settings():
        return validate_settings({
            "separator": SEPARATORS[cmds.optionMenuGrp(separator, query=True, select=True) - 1],
            "digits": cmds.intFieldGrp(digits, query=True, value1=True),
            "start": cmds.intFieldGrp(start, query=True, value1=True),
        })

    def refresh(*unused):
        if not cmds.textField(preview, exists=True):
            return
        if _saving:
            return
        try:
            current = read_settings()
            base = _scene_path()
            path = next_path(base, current) if base else "Choose a base name when saving."
            cmds.textField(preview, edit=True, text=path)
            cmds.text(status, edit=True, label="")
        except (ValueError, OSError) as error:
            cmds.textField(preview, edit=True, text="")
            cmds.text(status, edit=True, label=str(error))

    def apply(save_scene, *unused):
        try:
            current = read_settings()
            save_settings(current)
        except ValueError as error:
            cmds.text(status, edit=True, label=str(error))
            return
        if save_scene:
            _run_from_ui(settings=current)
            refresh()
        else:
            cmds.text(status, edit=True, label="Settings saved.")

    cmds.optionMenuGrp(separator, edit=True, changeCommand=refresh)
    for field in (digits, start):
        cmds.intFieldGrp(field, edit=True, changeCommand=refresh)
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(120, 230, 90))
    cmds.button(label="Save Settings", command=partial(apply, False))
    cmds.button(label="Increment and Save", command=partial(apply, True))
    cmds.button(label="Cancel", command=lambda *unused: cmds.deleteUI(WINDOW))
    available_events = cmds.scriptJob(listEvents=True)
    for event in ("SceneOpened", "NewSceneOpened", "SceneSaved", "SceneNameChanged"):
        if event in available_events:
            cmds.scriptJob(event=[event, refresh], parent=window)
    _refresh_options = refresh
    refresh()
    cmds.showWindow(window)
    return window


def uninstall(*args):
    """Remove the option box and restore the original Increment and Save action."""
    global _original_save_source, _option_item, _refresh_options
    _refresh_options = None
    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)
    for item in reversed(MENU_ITEMS):
        if cmds.menuItem(item, exists=True):
            cmds.deleteUI(item)
    if _option_item and cmds.menuItem(_option_item, exists=True):
        cmds.deleteUI(_option_item)
    _option_item = None
    if _original_save_source is not None:
        # Resolve the installed script afresh. Older versions could retain a
        # stale path after a failed reload or an in-session update.
        source = _native_save_source()
        mel.eval("source {};".format(json.dumps(source, ensure_ascii=False)))
        _original_save_source = None


def install(*args):
    """Attach options to Maya's existing Increment and Save menu action."""
    global _original_save_source, _option_item
    if cmds.about(batch=True):
        raise RuntimeError("Install the menu from an interactive Maya session.")
    if _original_save_source and _option_item and cmds.menuItem(_option_item, exists=True):
        cmds.menuItem(_option_item, edit=True, command=show_options)
        return
    source = _native_save_source()
    parent = mel.eval("global string $gMainFileMenu; $cisFileMenu = $gMainFileMenu;")
    mel.eval("buildFileMenu();")
    uninstall()
    items = cmds.menu(parent, query=True, itemArray=True) or []
    increment_item = next((
        item for item in items
        if (cmds.menuItem(item, query=True, command=True) or "").strip().rstrip(";")
        == "IncrementAndSave"
    ), None)
    if increment_item is None:
        raise RuntimeError("Could not locate Maya's Increment and Save menu item.")
    _original_save_source = source
    try:
        # The default runtime command is protected. It calls this MEL procedure
        # from both the existing File menu row and Maya's existing hotkey.
        mel.eval(
            'global proc incrementAndSaveScene(int $force) { '
            'python("import custom_increment_save; custom_increment_save._run_from_ui()"); }'
        )
        # Generated names avoid Maya reusing a deleted option box's association.
        # Validate placement because Maya's insertAfter can count attached boxes.
        preceding_item = items[items.index(increment_item) - 1]
        for anchor in (increment_item, preceding_item, increment_item, preceding_item):
            created = cmds.menuItem(
                parent=parent, insertAfter=anchor, optionBox=True,
                annotation="Custom Increment and Save options", command=show_options,
            )
            _option_item = created.rsplit("|", 1)[-1]
            updated = cmds.menu(parent, query=True, itemArray=True)
            if updated[updated.index(_option_item) - 1] == increment_item:
                break
            cmds.deleteUI(_option_item)
            _option_item = None
        else:
            raise RuntimeError("Maya could not place the option box beside Increment and Save.")
    except Exception:
        uninstall()
        raise
    print("Custom options attached to File > Increment and Save.")


if __name__ == "__main__":
    install()
    show_options()
