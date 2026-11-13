"""Extract the whole package, then drag this file into Maya's viewport."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

from maya import cmds, mel

PLUGIN = "customIncrementSavePlugin"
PAYLOAD = ("scripts/custom_increment_save.py", "plug-ins/customIncrementSavePlugin.py")


def _write_file(path, contents):
    """Replace one file only after its full contents have reached disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".cis-install-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(source_directory=None, modules_directory=None, autoload=True):
    """Install for this user. Optional directories support isolated verification."""
    if int(cmds.about(version=True).split()[0]) < 2023:
        raise RuntimeError("Custom Increment and Save requires Maya 2023 or newer.")
    source = Path(source_directory or Path(__file__).resolve().parent)
    contents = {relative: (source / relative).read_bytes() for relative in PAYLOAD}
    modules = Path(modules_directory or Path(cmds.internalVar(userAppDir=True)) / "modules")
    destination = modules / "CustomIncrementSave"
    manifest = modules / "CustomIncrementSave.mod"
    plugin_path = destination / "plug-ins" / (PLUGIN + ".py")
    previous_files = {
        destination / relative: (destination / relative).read_bytes()
        if (destination / relative).exists() else None for relative in PAYLOAD
    }
    previous_files[manifest] = manifest.read_bytes() if manifest.exists() else None
    registered = cmds.pluginInfo(PLUGIN, query=True, registered=True)
    was_loaded = registered and cmds.pluginInfo(PLUGIN, query=True, loaded=True)
    previous_plugin_path = cmds.pluginInfo(PLUGIN, query=True, path=True) if registered else None
    previous_autoload = cmds.pluginInfo(PLUGIN, query=True, autoload=True) if registered else False
    old_tool = sys.modules.get("custom_increment_save")
    if old_tool is not None:
        # Repair a 1.0.0 hook whose source metadata was lost before unloading it.
        spec = importlib.util.spec_from_file_location(
            "_cis_install_recovery", str(source / "scripts/custom_increment_save.py")
        )
        recovery = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recovery)
        description = mel.eval('whatIs "incrementAndSaveScene";')
        if getattr(old_tool, "_original_save_source", None) or "entered interactively" in description:
            old_tool._original_save_source = recovery._native_save_source()
    standalone_active = bool(getattr(old_tool, "_original_save_source", None)) and not was_loaded
    if was_loaded:
        cmds.unloadPlugin(PLUGIN)
    elif standalone_active:
        old_tool.uninstall()
    old_search_path = list(sys.path)
    old_plugin_path = os.environ.get("MAYA_PLUG_IN_PATH")
    old_maya_plugin_path = mel.eval('getenv "MAYA_PLUG_IN_PATH";')
    try:
        for relative, data in contents.items():
            _write_file(destination / relative, data)
        _write_file(manifest, b"+ CustomIncrementSave 1.0.1 ./CustomIncrementSave\n")
        scripts = str(destination / "scripts")
        # Maya's drop handler removes its temporary search path with pop(0).
        # Preserve that entry until the drop handler returns.
        source_is_first = bool(sys.path) and Path(sys.path[0]).resolve() == source.resolve()
        sys.path.insert(1 if source_is_first else 0, scripts)
        plugin_directory = str(plugin_path.parent)
        paths = (old_plugin_path or "").split(os.pathsep)
        if plugin_directory not in paths:
            os.environ["MAYA_PLUG_IN_PATH"] = os.pathsep.join([plugin_directory] + paths)
        # Maya and Python can use separate CRT environment caches on Windows.
        # Update Maya's search path too, so Plug-in Manager can discover it now.
        mel.eval('putenv "MAYA_PLUG_IN_PATH" {};'.format(json.dumps(
            os.environ.get("MAYA_PLUG_IN_PATH", "").replace("\\", "/")
        )))
        sys.modules.pop("custom_increment_save", None)
        importlib.invalidate_caches()
        cmds.loadPlugin(str(plugin_path), quiet=True)
        if not cmds.pluginInfo(PLUGIN, query=True, loaded=True):
            raise RuntimeError("Maya could not initialize Custom Increment and Save. Check the Script Editor.")
        if not cmds.about(batch=True):
            sys.modules["custom_increment_save"].install()
        cmds.pluginInfo(PLUGIN, edit=True, autoload=autoload)
        if not cmds.about(batch=True):
            cmds.pluginInfo(savePluginPrefs=True)
    except Exception:
        if cmds.pluginInfo(PLUGIN, query=True, loaded=True):
            cmds.unloadPlugin(PLUGIN)
        for path, data in previous_files.items():
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                _write_file(path, data)
        sys.path[:] = old_search_path
        if old_plugin_path is None:
            os.environ.pop("MAYA_PLUG_IN_PATH", None)
        else:
            os.environ["MAYA_PLUG_IN_PATH"] = old_plugin_path
        mel.eval('putenv "MAYA_PLUG_IN_PATH" {};'.format(json.dumps(
            old_maya_plugin_path.replace("\\", "/")
        )))
        sys.modules.pop("custom_increment_save", None)
        if old_tool is not None:
            sys.modules["custom_increment_save"] = old_tool
        if was_loaded:
            cmds.loadPlugin(previous_plugin_path, quiet=True)
            cmds.pluginInfo(PLUGIN, edit=True, autoload=previous_autoload)
        elif standalone_active:
            old_tool.install()
        raise
    print("Custom Increment and Save installed at {}".format(destination))
    return str(destination)


def onMayaDroppedPythonFile(*args):
    try:
        install()
    except Exception as error:
        cmds.confirmDialog(title="Installation failed", message=str(error), button=["OK"])
        raise
    cmds.confirmDialog(
        title="Custom Increment and Save installed",
        message="Open File > Increment and Save and click the little option box.\n\n"
                "Toggle customIncrementSavePlugin.py in Windows > Settings/Preferences > "
                "Plug-in Manager. Auto load is enabled.",
        button=["OK"],
    )
    return True


if __name__ == "__main__":
    onMayaDroppedPythonFile()
