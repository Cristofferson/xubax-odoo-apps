# -*- coding: utf-8 -*-
# XUBAX - WhatsApp Conversations

MESSAGES_MENU_NAMES = {"es": "Mensajes uno por uno"}
MESSAGES_MENU_NATIVE = {"es": "Mensajes"}


def _name_messages_menu(env, names, english):
    menu = env.ref("whatsapp.whatsapp_message_menu", raise_if_not_found=False)
    if not menu:
        return menu
    menu.with_context(lang="en_US").name = english
    for code, _name in env["res.lang"].get_installed():
        text = names.get(code.split("_")[0])
        if text:
            menu.with_context(lang=code).name = text
    return menu


def post_init_hook(env):
    """Fill the conversation list for the chats that already exist (date of the last
    WhatsApp message and whether the customer wrote it), and name the native list that
    moved under «Reports» in the installed languages."""
    env["discuss.channel"].search([("channel_type", "=", "whatsapp")])._xb_wac_refresh()
    _name_messages_menu(env, MESSAGES_MENU_NAMES, "Messages one by one")


def uninstall_hook(env):
    """Put the native «Messages» menu back before «Reports» goes away (child menus are
    deleted with their parent)."""
    menu = _name_messages_menu(env, MESSAGES_MENU_NATIVE, "Messages")
    root = env.ref("whatsapp.whatsapp_menu_main", raise_if_not_found=False)
    if menu and root:
        menu.write({"parent_id": root.id, "sequence": 1})
