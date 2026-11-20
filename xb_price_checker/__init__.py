from . import controllers
from . import models
from . import manual


def post_init_hook(env):
    """Ship the manual as a Knowledge article, where Knowledge exists."""
    manual.install_manual(env)
