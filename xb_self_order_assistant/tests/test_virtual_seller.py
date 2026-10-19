# -*- coding: utf-8 -*-
import json
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


def _block(**kw):
    """A content block as the Anthropic client returns it."""
    kw.setdefault("model_dump", lambda exclude_none=True, _kw=dict(kw): {
        k: v for k, v in _kw.items() if k != "model_dump"})
    return SimpleNamespace(**kw)


def _response(blocks, stop="end_turn"):
    usage = SimpleNamespace(input_tokens=1000, output_tokens=100,
                            cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage)


class _FakeClient:
    """Plays a scripted conversation instead of calling Anthropic."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script.pop(0)


@tagged("post_install", "-at_install")
class TestVirtualSeller(SelfOrderCommonTest):

    def setUp(self):
        super().setUp()
        self.pos_config.write({
            "self_ordering_mode": "kiosk",
            "xb_va_enabled": True,
            "xb_va_name": "Ana",
            "xb_va_ho_user_ids": [(6, 0, [self.env.ref("base.user_admin").id])],
            "xb_va_ho_discuss": True,
            "xb_va_ho_pos": False,
            "self_ordering_default_user_id": self.pos_user.id,
        })
        self.env["ir.config_parameter"].sudo().set_param("xb_self_order_assistant.anthropic_key", "test-key")
        self.pos_config.with_user(self.pos_user).open_ui()
        self.product = self.cola.product_tmpl_id
        self.product.write({"name": "Coca-Cola Zero Sugar", "self_order_available": True})

    def _conversation(self):
        return self.env["xb.va.conversation"].create({"config_id": self.pos_config.id})

    def _rpc(self, route, **params):
        params.setdefault("access_token", self.pos_config.access_token)
        response = self.url_open(route, data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
                                 headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 200, response.text[:300])
        return response.json()

    def test_kiosk_receives_the_settings(self):
        """The kiosk gets the seller's name and texts; nothing when it is off."""
        settings = self.pos_config._xb_va_settings()
        self.assertEqual(settings["name"], "Ana")
        self.assertIn("Ana", settings["greeting"])
        self.assertTrue(settings["available"])
        self.pos_config.xb_va_enabled = False
        self.assertFalse(self.pos_config._xb_va_settings())

    def test_voice_follows_gender(self):
        self.pos_config.xb_va_gender = "male"
        self.pos_config._onchange_xb_va_gender()
        self.assertEqual(self.pos_config.xb_va_voice_id.gender, "male")

    def test_search_only_in_this_kiosk(self):
        """The seller finds the kiosk's products and never the ones hidden from it."""
        conv = self._conversation()
        found = conv._xb_va_search("cola zero")
        self.assertIn(self.product.id, [p["id"] for p in found])
        self.product.self_order_available = False
        self.assertNotIn(self.product.id, [p["id"] for p in conv._xb_va_search("cola zero")])
        self.assertFalse(conv._xb_va_product(self.product.id))

    def test_conversation_with_tools(self):
        """Search, show cards, answer: the screen gets the products and the cost is kept."""
        conv = self._conversation()
        client = _FakeClient([
            _response([_block(type="tool_use", id="t1", name="buscar_productos", input={"texto": "cola"})], "tool_use"),
            _response([_block(type="tool_use", id="t2", name="mostrar_productos",
                              input={"producto_ids": [self.product.id, 999999]})], "tool_use"),
            _response([_block(type="text", text="Te muestro la Coca-Cola Zero.")]),
        ])
        with patch("anthropic.Anthropic", return_value=client):
            result = conv._xb_va_answer("Quiero un refresco sin azúcar")
        self.assertEqual(result["reply"], "Te muestro la Coca-Cola Zero.")
        self.assertEqual(result["products"], [self.product.id], "Unknown ids are dropped")
        self.assertEqual(conv.turns, 1)
        self.assertIn(self.product, conv.product_ids)
        self.assertGreater(conv.cost_usd, 0)
        self.assertIn("Quiero un refresco", conv.transcript)
        # The search result went back to the model as the answer to its tool call.
        results = [block for msg in client.calls[-1]["messages"] if msg["role"] == "user"
                   and isinstance(msg["content"], list) for block in msg["content"]]
        search = next(b for b in results if b["tool_use_id"] == "t1")
        self.assertIn("Coca-Cola Zero", search["content"])

    def test_call_a_person(self):
        """Asking for a person posts in the kiosk's chat with the people who attend."""
        conv = self._conversation()
        client = _FakeClient([
            _response([_block(type="tool_use", id="t1", name="llamar_persona",
                              input={"resumen": "Quiere un descuento"})], "tool_use"),
            _response([_block(type="text", text="Ya avisé a la tienda.")]),
        ])
        with patch("anthropic.Anthropic", return_value=client):
            result = conv._xb_va_answer("¿Me hacen descuento?")
        self.assertTrue(result["handoff"])
        self.assertTrue(conv.handoff)
        channel = self.env["discuss.channel"].sudo().search([("xb_va_config_id", "=", self.pos_config.id)])
        self.assertEqual(len(channel), 1)
        self.assertIn(self.env.ref("base.user_admin").partner_id, channel.channel_member_ids.partner_id)
        self.assertIn("Quiere un descuento", channel.message_ids[:1].body)

    def test_daily_limit(self):
        """Over the daily limit the button hides and the route answers without the AI."""
        self.pos_config.xb_va_daily_limit = 1.0
        conv = self._conversation()
        conv.cost_usd = 2.0
        self.assertFalse(self.pos_config._xb_va_settings()["available"])
        body = self._rpc("/xb-va/%s/chat" % self.pos_config.id, text="Hola")
        self.assertTrue(body["result"]["unavailable"])

    def test_routes_need_the_kiosk_token(self):
        body = self._rpc("/xb-va/%s/chat" % self.pos_config.id, access_token="wrong", text="Hola")
        self.assertIn("error", body)
        self.pos_config.xb_va_enabled = False
        body = self._rpc("/xb-va/%s/chat" % self.pos_config.id, text="Hola")
        self.assertIn("error", body)

    def test_spoken_name(self):
        """A name written in a special way is said as configured; the audio is kept."""
        self.pos_config.write({"xb_va_name": "AnelIA", "xb_va_name_say": "Anelia"})
        self.env["ir.config_parameter"].sudo().set_param("xb_self_order_assistant.openai_key", "test-key")
        sent = {}

        def fake_post(url, headers=None, data=None, timeout=None, **kw):
            sent.update(json.loads(data))
            return SimpleNamespace(content=b"ID3" + b"0" * 9000, raise_for_status=lambda: None)

        Conv = self.env["xb.va.conversation"]
        with patch("odoo.addons.xb_self_order_assistant.models.va_conversation.requests.post", fake_post):
            audio, new = Conv._xb_va_speech(self.pos_config, "Hola, soy AnelIA.")
            again, new_again = Conv._xb_va_speech(self.pos_config, "Hola, soy AnelIA.")
        self.assertEqual(sent["input"], "Hola, soy Anelia.")
        self.assertTrue(audio.startswith(b"ID3"))
        self.assertTrue(new)
        self.assertFalse(new_again, "The second time comes from the saved audio")
        self.assertEqual(again, audio)




    def test_live_session(self):
        """Instant conversation: Odoo asks OpenAI for a short-lived key with the seller's rules and tools."""
        self.pos_config.write({"xb_va_engine": "realtime", "xb_va_rt_model": "gpt-realtime-2.1-mini"})
        self.env["ir.config_parameter"].sudo().set_param("xb_self_order_assistant.openai_key", "test-key")
        sent = {}

        def fake_post(url, headers=None, data=None, timeout=None, **kw):
            sent["url"] = url
            sent["body"] = json.loads(data)
            return SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"value": "ek_test", "expires_at": 123})

        with patch("odoo.addons.xb_self_order_assistant.models.va_conversation.requests.post", fake_post):
            body = self._rpc("/xb-va/%s/live" % self.pos_config.id)["result"]
        self.assertTrue(body["ok"])
        self.assertEqual(body["key"], "ek_test")
        self.assertTrue(sent["url"].endswith("/realtime/client_secrets"))
        session = sent["body"]["session"]
        self.assertEqual(session["model"], "gpt-realtime-2.1-mini")
        self.assertIn("Ana", session["instructions"])
        self.assertIn("buscar_productos", [t["name"] for t in session["tools"]])
        self.assertEqual(session["audio"]["output"]["voice"], "coral", "Nova does not exist live: closest voice")
        conv = self.env["xb.va.conversation"].search([("token", "=", body["token"])])
        # The model asks Odoo to search; what was said and what it used are kept.
        tool = self._rpc("/xb-va/%s/tool" % self.pos_config.id, token=conv.token,
                         name="buscar_productos", args={"texto": "cola zero"})["result"]
        self.assertIn("Coca-Cola Zero", tool["output"])
        self._rpc("/xb-va/%s/tool" % self.pos_config.id, token=conv.token, name="unknown", args={})
        self._rpc("/xb-va/%s/live_log" % self.pos_config.id, token=conv.token, who="customer", text="Hola")
        self._rpc("/xb-va/%s/live_log" % self.pos_config.id, token=conv.token, usage={
            "input_token_details": {"audio_tokens": 1000, "text_tokens": 2000, "cached_tokens": 500},
            "output_token_details": {"audio_tokens": 400, "text_tokens": 50}})
        conv.invalidate_recordset()
        self.assertEqual(conv.turns, 1)
        self.assertIn("Hola", conv.transcript)
        self.assertEqual(conv.rt_audio_in, 1000)
        self.assertGreater(conv.cost_usd, 0)

    def test_cart_and_scan(self):
        """The seller puts a product in the cart (asking for missing options) and recognizes a barcode."""
        conv = self._conversation()
        ui = conv._xb_va_new_ui()
        text, error = conv._xb_va_run_tool("agregar_al_carrito", {"producto_id": self.product.id, "cantidad": 2}, ui)
        self.assertFalse(error, text)
        self.assertEqual(ui["actions"], [{"type": "add_to_cart", "template_id": self.product.id, "ptav_ids": [], "qty": 2}])
        ui = conv._xb_va_new_ui()
        conv._xb_va_run_tool("ir_a_pagar", {}, ui)
        self.assertEqual(ui["actions"][0]["type"], "go_cart")
        self.product.barcode = "7501234567890"
        found = conv._xb_va_scan("7501234567890")
        self.assertEqual(found["open"], self.product.id)
        self.assertIn("Coca-Cola Zero", found["text"])
        self.assertFalse(conv._xb_va_scan("nada-que-ver")["open"])

    def test_take_it_to_the_phone(self):
        """The conversation moves to the customer's phone with its own key, only that conversation."""
        conv = self._conversation()
        conv.transcript = "Cliente: Hola\nAna: Hola, ¿qué buscas?\n"
        ui = conv._xb_va_new_ui()
        text, error = conv._xb_va_run_tool("llevar_al_celular", {}, ui)
        self.assertFalse(error, text)
        url = ui["actions"][0]["url"]
        mobile = url.rsplit("/", 1)[1]
        self.assertEqual(self.env["xb.va.conversation"]._xb_va_mobile(mobile), conv)
        page = self.url_open("/xb-va/m/%s" % mobile)
        self.assertEqual(page.status_code, 200)
        conv.invalidate_recordset()
        self.assertEqual(conv.presence, "phone")
        names = [t["name"] for t in conv._xb_va_tools()]
        self.assertNotIn("agregar_al_carrito", names, "No kiosk cart on the phone")
        history = self._rpc("/xb-va/%s/history" % self.pos_config.id, access_token=None, m=mobile)["result"]
        self.assertEqual([m["text"] for m in history["messages"]], ["Hola", "Hola, ¿qué buscas?"])
        # The key opens only this conversation, and not the kiosk's others.
        other = self._conversation()
        body = self._rpc("/xb-va/%s/history" % self.pos_config.id, access_token=None, m=mobile, token=other.token)
        self.assertEqual(len(body["result"]["messages"]), 2)
        self.assertIn("error", self._rpc("/xb-va/%s/history" % self.pos_config.id, access_token=None, m="x" * 40))
        conv.mobile_expires = "2020-01-01 00:00:00"
        self.assertEqual(self.url_open("/xb-va/m/%s" % mobile).status_code, 404)

    def test_kiosk_nfc_sticker(self):
        """The kiosk's NFC sticker takes the conversation going on to the phone (or starts one there)."""
        url = self.pos_config.xb_va_tap_url
        self.assertIn("/xb-va/k/%s/" % self.pos_config.id, url)
        path = url.split(self.pos_config.get_base_url(), 1)[1]
        conv = self._conversation()
        conv.last_dt = "2099-01-01 00:00:00"
        resp = self.url_open(path, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        conv.invalidate_recordset()
        self.assertIn("/xb-va/m/%s" % conv.sudo().mobile_token, resp.headers["Location"])
        self.assertEqual(self.url_open(path[:-3] + "xyz", allow_redirects=False).status_code, 404)

    def test_report_and_weekly_summary(self):
        """Searches (and what was not found), cart, sale credited to the conversation, weekly e-mail."""
        conv = self._conversation()
        conv.write({"turns": 2, "last_dt": "2099-01-01 00:00:00"})
        conv._xb_va_run_tool("buscar_productos", {"texto": "cola zero"}, conv._xb_va_new_ui())
        conv._xb_va_run_tool("buscar_productos", {"texto": "unicornio dorado"}, conv._xb_va_new_ui())
        conv._xb_va_run_tool("agregar_al_carrito", {"producto_id": self.product.id}, conv._xb_va_new_ui())
        self.assertEqual(sorted(conv.search_ids.mapped("found")), [False, True])
        self.assertTrue(conv.cart_added)
        linked = self.env["xb.va.conversation"]._xb_va_link_sale(self.pos_config, 120.0, "S00001")
        self.assertEqual(linked, conv)
        self.assertTrue(conv.converted)
        self.assertEqual(conv.sale_amount, 120.0)
        admin = self.env.ref("base.user_admin")
        admin.email = "owner@example.com"
        self.pos_config.xb_va_ho_user_ids = admin
        numbers = self.pos_config._xb_va_week_numbers("2000-01-01 00:00:00")
        self.assertEqual(numbers["sales"], 1)
        self.assertEqual(numbers["missing"], [("unicornio dorado", 1)])
        self.env["pos.config"]._cron_xb_va_weekly_digest()
        mail = self.env["mail.mail"].search([("subject", "ilike", self.pos_config.name)], order="id desc", limit=1)
        self.assertTrue(mail)
        self.assertIn("unicornio dorado", mail.body_html)
        self.assertEqual(mail.email_to, "owner@example.com")
