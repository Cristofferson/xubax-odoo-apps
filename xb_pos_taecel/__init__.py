# -*- coding: utf-8 -*-
from . import const
from . import models
from . import manual


def post_init_hook(env):
    """Ship the cashier manual as a Knowledge article, where Knowledge exists."""
    manual.install_manual(env)
