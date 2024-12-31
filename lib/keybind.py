# -*- coding: utf-8 -*-
from . import util

def _make_bind(key_id, bound_action_name, bound_action_args=''):
    """Function factory for onAction() keybind decorators"""
    def decorator(onAction):
        def wrapper(self, action):
            if key_id is not None and action.getButtonCode() == int(key_id) and hasattr(self, bound_action_name):
                bound_action = 'self.{}({})'.format(bound_action_name, bound_action_args)
                eval(bound_action)
            else:
                onAction(self, action)
        return wrapper
    return decorator

home = _make_bind(util.HOME_BUTTON_MAPPED, 'goHome', 'with_root=True')
search = _make_bind(util.SEARCH_BUTTON_MAPPED, 'searchButtonClicked')
toggle_subtitles = _make_bind(61524, 'toggleSubtitles')
