"""Maya Plug-in Manager entry for Custom Increment and Save."""
import sys
import importlib
from pathlib import Path
from functools import partial

from maya import cmds, utils
from maya.api import OpenMaya

tool = None
_active = False
_generation = 0


def maya_useNewAPI():
    pass


def _enable_ui(generation):
    if _active and generation == _generation:
        tool.install()


def initializePlugin(plugin_object):
    global _active, _generation, tool
    plugin = OpenMaya.MFnPlugin(plugin_object, "Custom Increment and Save", "1.0.1", "Any")
    scripts = str(Path(plugin.loadPath()).parent / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    tool = importlib.import_module("custom_increment_save")
    cmds.pluginInfo(plugin.name(), edit=True, writeRequires=False)
    _active = True
    _generation += 1
    if not cmds.about(batch=True):
        # During Auto load, Maya can still be constructing its native menus.
        utils.executeDeferred(partial(_enable_ui, _generation))


def uninitializePlugin(plugin_object):
    global _active, _generation
    _active = False
    _generation += 1
    if not cmds.about(batch=True):
        tool.uninstall()
