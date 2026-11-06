import os

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# XPago speaks only to the XPago API: the processor behind it is never named in the apps.
FORBIDDEN = 'com' + 'pago'


@tagged('post_install', '-at_install')
class TestNoProcessorName(TransactionCase):

    def test_processor_is_not_named_anywhere(self):
        found = []
        for module in ('xpago', 'xpago_self_order'):
            root = get_module_path(module)
            if not root:
                continue
            for folder, _dirs, files in os.walk(root):
                for name in files:
                    if name.endswith(('.png', '.jpg', '.webp', '.gif', '.pyc', '.woff2')):
                        continue
                    path = os.path.join(folder, name)
                    with open(path, encoding='utf-8', errors='ignore') as file:
                        if FORBIDDEN in file.read().lower():
                            found.append(os.path.relpath(path, root))
        self.assertEqual(found, [])
