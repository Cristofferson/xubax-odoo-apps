# -*- coding: utf-8 -*-
"""Wire-level constants for the TAECEL REST API.

Everything TAECEL-specific that could change lives here on purpose. Correcting
this single file re-points the whole module; no model or POS code hard-codes an
endpoint, a field name or a magic id.

Provenance of every value is marked:
    CONFIRMED -- documented in the integrator manual we hold ("Manual TAECEL",
                 getProducts / getSales / RegistroCuenta / ReportarCompra).
    PENDING   -- the transactional API (dispatch a recharge, query one
                 transaction, read a wallet balance) is a SEPARATE document
                 TAECEL issues after the "Levantamiento Tecnologico" + test
                 verification. We do not hold it yet. These values are our best
                 working guess and MUST be checked against that manual before
                 going live. Nothing PENDING is reachable from the POS today.

All calls are POST, ``application/x-www-form-urlencoded``, authenticated with
``key`` + ``nip`` on every request. (CONFIRMED.)
"""

# --- Base URL --------------------------------------------------------------
# CONFIRMED. The manual's samples all hit https://taecel.com/app/api/<method>.
# TAECEL hands out a distinct test base URL with the test credentials.
DEFAULT_URL_PROD = 'https://taecel.com/app/api'
DEFAULT_URL_TEST = 'https://taecel.com/app/api'

# --- Credential parameters (CONFIRMED) -------------------------------------
PARAM_KEY = 'key'
PARAM_NIP = 'nip'

# --- Endpoints -------------------------------------------------------------
# CONFIRMED -- documented in the manual we hold.
PATH_PRODUCTS = 'getProducts'          # full catalog
PATH_SALES = 'getSales'                # sales history (params: fecha, bolsa)
PATH_REGISTER = 'RegistroCuenta'       # register an affiliate sub-account
PATH_REPORT_BUY = 'public/ReportarCompra'   # report a bank deposit (funding)
PATH_REPORT_URL = 'urlReporteCompra'   # this account's deposit reference + form

# urlReporteCompra response. VERIFIED LIVE: this endpoint is the odd one out --
# it answers with a FLAT dict, with no success/error/message/data envelope
# around it, so the generic parsing cannot judge it. Read the raw payload.
K_REPORT_REF = 'refCompra'             # bank reference to deposit against
K_REPORT_URL = 'urlReporte'            # pre-authenticated "report a deposit" form

# CONFIRMED -- transactional API, documented in the manual (image pages of
# "Manual TAECEL", API Integracion) and validated live against the test account.
PATH_REQUEST = 'RequestTXN'            # dispatch a recharge/payment -> transID
PATH_STATUS = 'StatusTXN'             # query one transaction by transID
PATH_BALANCE = 'getBalance'           # read wallet balances directly (per bolsa)

# RequestTXN request params (besides key/nip). 'monto' only for free-amount
# (Tipo 1) carriers; ignored on fixed-price catalog products. 'refCte' is our
# own reference, echoed back in getSales.
PARAM_PRODUCT = 'producto'
PARAM_REFERENCE = 'referencia'
PARAM_AMOUNT = 'monto'
PARAM_REF_CLIENTE = 'refCte'
PARAM_TRANS_ID = 'transID'

# RequestTXN response data key.
K_TXN_TRANS_ID = 'transID'             # handle to feed StatusTXN

# StatusTXN response: VERIFIED LIVE that its ``data`` uses the SAME capitalised
# keys as a getSales row (Status, Folio, 'Saldo Final', Nota, pin, Monto...),
# NOT the lowercase keys the manual's screenshot suggested. Crucially,
# top-level ``success:true`` only means the QUERY worked -- the recharge outcome
# is ``data.Status``: 'Exitosa' | 'Fracasada' | 'En proceso'. So StatusTXN is
# settled by the very same code as getSales (_settle_from_sale, K_SALE_* keys).
STATUS_IN_PROGRESS = 'en proceso'      # keep polling; not yet terminal

# getBalance response: data is a list of {ID, Bolsa, Saldo}.
K_BAL_BOLSA_ID = 'ID'
K_BAL_SALDO = 'Saldo'

# Polling StatusTXN after a dispatch. The manual loops StatusTXN while the
# provider is still working and TimeOut < 60. We poll on a modest budget and,
# if still unresolved, park the transaction for the getSales reconciler rather
# than block the cashier (or a cron worker) any longer. Never re-dispatched.
DISPATCH_POLL_INTERVAL = 3             # seconds between StatusTXN queries
DISPATCH_POLL_MAX = 45                 # give up polling after this many seconds

# --- Response envelope (CONFIRMED) -----------------------------------------
# {"success": bool, "error": int, "message": str, "data": {...} | [...]}
RESP_SUCCESS = 'success'
RESP_ERROR = 'error'
RESP_MESSAGE = 'message'
RESP_DATA = 'data'

# --- Wallets / "bolsas" (CONFIRMED) ----------------------------------------
# getProducts.data.bolsas lists them; RegistroCuenta confirms a third. They are
# funded through different bank accounts and balances are NOT transferable, so
# the module tracks each independently instead of summing them.
BOLSA_AIRTIME = '1'      # Tiempo Aire
BOLSA_SERVICES = '2'     # Pago de Servicios
BOLSA_CFDI = '3'         # Timbres CFDI

BOLSA_NAMES = {
    BOLSA_AIRTIME: 'Tiempo Aire',
    BOLSA_SERVICES: 'Pago de Servicios',
    BOLSA_CFDI: 'Timbres CFDI',
}

# --- Carrier type (CONFIRMED: carriersTipo) --------------------------------
# Drives POS behaviour: a catalog carrier shows fixed-amount buttons; a
# free-amount carrier shows a numeric field the cashier fills in.
CARRIER_CATALOG = '0'    # montos fijos y predefinidos (productos)
CARRIER_FREE = '1'       # monto libre

# --- Input field format (CONFIRMED: formatoCampos) -------------------------
# Each carrier ships a `Campos` spec used to validate the reference the cashier
# types (phone number, account, bill reference) *before* charging the customer.
FORMATO_NUMERIC = '1'
FORMATO_ALPHANUM = '2'
FORMATO_EMAIL = '3'

# --- getProducts payload keys (CONFIRMED) ----------------------------------
# Carrier object.
K_CARRIER_ID = 'ID'
K_CARRIER_NAME = 'Nombre'
K_CARRIER_LOGO = 'Logotipo'
K_CARRIER_BOLSA = 'BolsaID'
K_CARRIER_CATEG = 'Categoria'
K_CARRIER_CATEG_ID = 'CategoriaID'
K_CARRIER_TYPE = 'Tipo'
K_CARRIER_FIELDS = 'Campos'
# Field (Campos[]) object.
K_FIELD_NAME = 'Nombre'
K_FIELD_KEY = 'Campo'
K_FIELD_MIN = 'Min'
K_FIELD_MAX = 'Max'
K_FIELD_FORMAT = 'Formato'
K_FIELD_REQUIRED = 'Obligatorio'
K_FIELD_CONFIRM = 'Confirmar'
K_FIELD_LEADING_ZERO = 'iniCero'
# Product object.
K_PROD_CODE = 'Codigo'
K_PROD_AMOUNT = 'Monto'
K_PROD_CARRIER = 'Carrier'
K_PROD_CARRIER_ID = 'CarrierID'
K_PROD_BOLSA = 'BolsaID'
K_PROD_CATEG = 'Categoria'
K_PROD_CATEG_ID = 'CategoriaID'
K_PROD_NAME = 'Nombre'
K_PROD_DESC = 'Descripcion'
K_PROD_VIGENCIA = 'Vigencia'
K_PROD_UNITS = 'Unidades'
K_PROD_ID = 'proID'
K_PROD_SUBSCRIPTION = 'suscrip'

# --- getSales payload keys (CONFIRMED) -------------------------------------
# The reconciliation source we CAN use today: it lists real transactions with
# their final status and the wallet balance after each one.
K_SALE_TRANS_ID = 'TransID'
K_SALE_DATE = 'Fecha'
K_SALE_CARRIER = 'Carrier'
K_SALE_PHONE = 'Telefono'
K_SALE_FOLIO = 'Folio'
K_SALE_STATUS = 'Status'      # 'Exitosa' | 'Fracasada'
K_SALE_AMOUNT = 'Monto'
K_SALE_NOTE = 'Nota'
K_SALE_PIN = 'pin'
K_SALE_BOLSA = 'Bolsa'
K_SALE_FINAL_BALANCE = 'Saldo Final'

# getSales.Status values (note: TAECEL pads 'Fracasada ' with a space).
SALE_STATUS_OK = 'exitosa'
SALE_STATUS_KO = 'fracasada'

# --- Local transaction states ----------------------------------------------
# 'timeout' is not an error: TAECEL may already have dispatched. It is resolved
# by RE-QUERYING (getSales, or the PENDING StatusTXN), never by re-dispatching.
STATE_DRAFT = 'draft'
STATE_SENT = 'sent'
STATE_DONE = 'done'
STATE_FAILED = 'failed'
STATE_TIMEOUT = 'timeout'

# --- Operational rules (CONFIRMED, commercial docs) ------------------------
BILL_MIN_HOURS_BEFORE_DUE = 48   # bills collectable only >48h before due date
REFUNDS_ALLOWED = False          # sales are final once dispatched

# Network timeout (seconds). The cashier is at the till; anything slower is
# parked for reconciliation rather than kept waiting.
DEFAULT_TIMEOUT = 25
