# -*- coding: utf-8 -*-
"""User-manual content, in English (source) and Spanish.

Each body is plain HTML that the Knowledge editor renders as-is. The English
label of every screen element is used so the manual matches the interface a
reader sees; the Spanish version uses the module's es_MX labels.
"""

ROOT = {
    "icon": "\U0001F4E6",  # 📦
    "name_en": "Products from Vendor Bills",
    "name_es": "Productos desde facturas de proveedor",
    "body_en": """
<p class="lead">When a vendor's electronic invoice arrives (the <strong>XML</strong>
file), Odoo already reads it and fills the bill for you. What it could not do was deal
with the <strong>products</strong>: if the item was not in your catalogue, the line was
left as a bare text label —no product, no cost, no inventory— and next month the same
thing happened again.</p>

<p>This application takes care of that part. It does three things:</p>

<ol>
  <li><strong>Recognises</strong> items by the code <em>that</em> vendor uses, not by your
      internal reference.</li>
  <li><strong>Proposes</strong> the ones you do not have, in a review screen where you
      decide whether to create them, link them to a product you already have, or reject
      them.</li>
  <li><strong>Learns</strong>: every decision you make is remembered, so the next bill
      from that vendor matches on its own.</li>
</ol>

<div class="alert alert-info">
  <p><strong>The one thing to understand.</strong> The application never invents products
  behind your back. By default everything unknown waits for your review in
  <em>Accounting &#9656; Vendors &#9656; Proposed Products</em>.</p>
</div>

<h2>Where everything is</h2>
<table class="table table-bordered">
  <tbody>
    <tr>
      <td style="width:38%"><strong>Proposed Products</strong></td>
      <td>Accounting &#9656; Vendors &#9656; Proposed Products<br/>
          <span class="text-muted">The day-to-day inbox.</span></td>
    </tr>
    <tr>
      <td><strong>Vendor Codes</strong></td>
      <td>Accounting &#9656; Vendors &#9656; Vendor Codes<br/>
          <span class="text-muted">The lookup table the application keeps learning.</span></td>
    </tr>
    <tr>
      <td><strong>Settings</strong></td>
      <td>Accounting &#9656; Configuration &#9656; Settings &#9656; <em>Products from Vendor Bills</em><br/>
          <span class="text-muted">For whoever administers the system.</span></td>
    </tr>
  </tbody>
</table>

<p>The sections of this manual are listed below. If this is your first time, reading
<strong>&laquo;Review the proposed products&raquo;</strong> is enough to get to work.</p>
""",
    "body_es": """
<p class="lead">Cuando llega la factura electrónica de un proveedor (el archivo
<strong>XML</strong>), Odoo ya sabe leerla y llenar la factura sola. Lo que no sabía hacer
era resolver los <strong>productos</strong>: si el artículo no estaba en el catálogo, el
renglón se quedaba como texto suelto —sin producto, sin costo y sin inventario— y al mes
siguiente volvía a pasar lo mismo.</p>

<p>Esta aplicación se encarga de esa parte. Hace tres cosas:</p>

<ol>
  <li><strong>Reconoce</strong> los artículos por el código que usa <em>ese</em> proveedor,
      no por nuestra referencia interna.</li>
  <li><strong>Propone</strong> los que no conocemos, en una bandeja donde tú decides si se
      crean, se ligan a un producto que ya tenemos, o se descartan.</li>
  <li><strong>Aprende</strong>: cada decisión que tomas queda guardada, así que la siguiente
      factura de ese proveedor ya empareja sola.</li>
</ol>

<div class="alert alert-info">
  <p><strong>Lo más importante de entender.</strong> La aplicación nunca inventa productos
  a tus espaldas. Por omisión todo lo desconocido se queda esperando tu revisión en
  <em>Contabilidad ▸ Proveedores ▸ Productos propuestos</em>.</p>
</div>

<h2>Dónde está todo</h2>
<table class="table table-bordered">
  <tbody>
    <tr>
      <td style="width:38%"><strong>Productos propuestos</strong></td>
      <td>Contabilidad ▸ Proveedores ▸ Productos propuestos<br/>
          <span class="text-muted">La bandeja del día a día.</span></td>
    </tr>
    <tr>
      <td><strong>Códigos de proveedor</strong></td>
      <td>Contabilidad ▸ Proveedores ▸ Códigos de proveedor<br/>
          <span class="text-muted">La tabla de equivalencias que la aplicación va aprendiendo.</span></td>
    </tr>
    <tr>
      <td><strong>Configuración</strong></td>
      <td>Contabilidad ▸ Configuración ▸ Ajustes ▸ <em>Productos desde facturas de proveedor</em><br/>
          <span class="text-muted">Solo para quien administra el sistema.</span></td>
    </tr>
  </tbody>
</table>

<p>Las secciones de este manual están listadas abajo. Si es tu primera vez, con leer
<strong>«Revisar los productos propuestos»</strong> ya puedes trabajar.</p>
""",
}


SECTIONS = [
    {
        "icon": "\U0001F4E5",  # 📥
        "name_en": "1. How a vendor bill comes in",
        "name_es": "1. Cómo entra una factura de proveedor",
        "body_en": """
<p>The module does not change how you capture bills. It only steps in when the bill
arrives as an <strong>electronic file</strong>, which is when Odoo can read the lines on
its own.</p>

<h2>The two ways to bring the XML in</h2>
<ol>
  <li><strong>Dropping the file.</strong> Go to
      <em>Accounting &#9656; Vendors &#9656; Bills</em> and drag the XML (or the PDF that
      carries the XML inside) onto the list. Odoo creates the bill and fills it.</li>
  <li><strong>By email.</strong> If the purchase journal has an email alias set up, just
      forward the vendor's email with its XML attached.</li>
</ol>

<h2>Which formats it understands</h2>
<ul>
  <li><strong>CFDI 4.0</strong> — the XML issued by Mexican vendors.</li>
  <li><strong>UBL, Factur-X, XRechnung, CII</strong> — the European electronic formats, in
      case you ever buy abroad.</li>
</ul>

<h2>What happens at that moment</h2>
<p>Line by line, the application:</p>
<ol>
  <li>Looks the item up by the <strong>vendor code</strong> in the lookup table (see
      <em>&laquo;The vendor codes&raquo;</em>).</li>
  <li>If it is not there, it tries Odoo's normal search: barcode, internal reference and
      name.</li>
  <li>If it finds it, it puts it on the line and —depending on the policy you chose—
      updates the cost.</li>
  <li>If it does <strong>not</strong> find it, it sends it to <em>Proposed Products</em>
      and leaves the line with the description that came on the XML.</li>
</ol>

<div class="alert alert-warning">
  <p><strong>The bill is never altered.</strong> The quantities, prices, discounts and
  taxes that came on the XML are always respected, even later when you link a product to
  the line. What the vendor billed is what stays.</p>
</div>

<h2>How to tell something is pending</h2>
<p>The bill shows a <strong>Proposed</strong> button at the top right, with a number, when
that bill left items waiting for review. That button takes you straight to them.</p>
""",
        "body_es": """
<p>El módulo no cambia la forma en que capturas facturas. Solo entra en acción cuando la
factura llega como <strong>archivo electrónico</strong>, que es cuando Odoo puede leer los
renglones por su cuenta.</p>

<h2>Las dos formas de meter el XML</h2>
<ol>
  <li><strong>Arrastrando el archivo.</strong> Ve a
      <em>Contabilidad ▸ Proveedores ▸ Facturas</em> y arrastra el XML (o el PDF que trae
      el XML dentro) sobre la lista. Odoo crea la factura y la llena.</li>
  <li><strong>Por correo.</strong> Si el diario de compras tiene un alias de correo
      configurado, basta con reenviar ahí el correo del proveedor con su XML adjunto.</li>
</ol>

<h2>Qué formatos entiende</h2>
<ul>
  <li><strong>CFDI 4.0</strong> — el XML que emiten los proveedores mexicanos.</li>
  <li><strong>UBL, Factur-X, XRechnung, CII</strong> — los formatos electrónicos europeos,
      por si alguna vez compras fuera.</li>
</ul>

<h2>Qué pasa en ese momento</h2>
<p>Renglón por renglón, la aplicación:</p>
<ol>
  <li>Busca el artículo por el <strong>código del proveedor</strong> en la tabla de
      equivalencias (ver <em>«Los códigos de proveedor»</em>).</li>
  <li>Si no lo encuentra ahí, prueba con la búsqueda normal de Odoo: código de barras,
      referencia interna y nombre.</li>
  <li>Si lo encuentra, lo pone en el renglón y —según la política que hayas elegido—
      actualiza el costo.</li>
  <li>Si <strong>no</strong> lo encuentra, lo manda a <em>Productos propuestos</em> y deja
      el renglón con la descripción que venía en el XML.</li>
</ol>

<div class="alert alert-warning">
  <p><strong>La factura no se altera.</strong> Las cantidades, los precios, los descuentos
  y los impuestos que traía el XML se respetan siempre, incluso cuando después ligas un
  producto al renglón. Lo que el proveedor facturó es lo que queda.</p>
</div>

<h2>Cómo saber si quedó algo pendiente</h2>
<p>En la factura aparece un botón arriba a la derecha que dice <strong>Propuestos</strong>
con un número, cuando esa factura dejó artículos esperando revisión. Ese botón te lleva
directo a ellos.</p>
""",
    },
    {
        "icon": "✅",  # ✅
        "name_en": "2. Review the proposed products",
        "name_es": "2. Revisar los productos propuestos",
        "body_en": """
<p>This is the day-to-day screen:
<em>Accounting &#9656; Vendors &#9656; Proposed Products</em>.
It opens filtered on <strong>&laquo;To review&raquo;</strong>, which is normally all you
care about.</p>

<h2>What each column is telling you</h2>
<table class="table table-bordered">
  <tbody>
    <tr><td style="width:26%"><strong>Vendor</strong></td>
        <td>Who billed it to you.</td></tr>
    <tr><td><strong>Vendor code</strong></td>
        <td>The reference <em>they</em> put on the item. It is the piece of data the
            application will recognise it by next time.</td></tr>
    <tr><td><strong>Description</strong></td>
        <td>Exactly as it was written on the XML, uncorrected.</td></tr>
    <tr><td><strong>Seen</strong></td>
        <td>On how many bills this item has already arrived. If it says 4, you are four
            bills into buying it without having it in the catalogue.</td></tr>
    <tr><td><strong>Last price</strong></td>
        <td>What it cost last time.</td></tr>
    <tr><td><strong>Product</strong></td>
        <td>Empty until you decide. This is where you pick an existing product if you
            already have the item under another name.</td></tr>
  </tbody>
</table>

<div class="alert alert-info">
  <p>The same item arriving on ten bills is <strong>one row</strong> with the counter at
  10, not ten rows. You review it once.</p>
</div>

<h2>The three decisions</h2>

<h3>Create product</h3>
<p>Use it when the item <strong>really is new</strong>. It creates the product with the
vendor's description, the configured category and type, saves the cost according to the
policy, and records the vendor code along the way.</p>

<h3>Link</h3>
<p>Use it when you <strong>already have</strong> the item, the vendor just calls it
something else. Pick the product in the <em>Product</em> column and press
<strong>Link</strong>. This is the most valuable thing you can do: you are teaching it the
match, and it will not ask you again.</p>

<h3>Reject</h3>
<p>For what is not a product: freight, down payments, roundings, credit notes, one-off
services. It is stored as rejected and stops showing in the pending list.</p>

<h2>What happens after you decide</h2>
<p>On create or link, the application <strong>goes back to the draft bills</strong> where
that item appeared and puts the product on the line. You do not have to hunt them down one
by one.</p>

<div class="alert alert-warning">
  <p>It only touches <strong>draft</strong> bills. A posted bill is not modified: if you
  need to fix it, it has to be set back to draft by hand.</p>
</div>

<h2>How to work fast</h2>
<ul>
  <li>Sort by <strong>Seen</strong>, high to low: what repeats most is what pays off to
      resolve first.</li>
  <li>Group by <strong>Vendor</strong> to clear everything from one supplier in one go.</li>
  <li>You can use the buttons straight from the list, without opening each row.</li>
  <li>If you got it wrong, open the row and use <strong>Back to review</strong>.</li>
</ul>
""",
        "body_es": """
<p>Ésta es la pantalla del día a día:
<em>Contabilidad ▸ Proveedores ▸ Productos propuestos</em>.
Llega filtrada en <strong>«Por revisar»</strong>, que es lo único que normalmente te
interesa.</p>

<h2>Qué te está diciendo cada columna</h2>
<table class="table table-bordered">
  <tbody>
    <tr><td style="width:26%"><strong>Proveedor</strong></td>
        <td>Quién te lo facturó.</td></tr>
    <tr><td><strong>Código del proveedor</strong></td>
        <td>La referencia que <em>él</em> le pone al artículo. Es el dato con el que la
            aplicación lo va a reconocer la próxima vez.</td></tr>
    <tr><td><strong>Descripción</strong></td>
        <td>Tal cual venía escrita en el XML, sin corregir nada.</td></tr>
    <tr><td><strong>Visto</strong></td>
        <td>En cuántas facturas ha llegado ya este artículo. Si dice 4, es que llevas
            cuatro facturas comprándolo sin tenerlo dado de alta.</td></tr>
    <tr><td><strong>Último precio</strong></td>
        <td>Lo que costó la última vez.</td></tr>
    <tr><td><strong>Producto</strong></td>
        <td>Vacío mientras no decidas. Aquí es donde eliges un producto existente si el
            artículo ya lo tienes con otro nombre.</td></tr>
  </tbody>
</table>

<div class="alert alert-info">
  <p>Un mismo artículo que llega en diez facturas es <strong>un solo renglón</strong> con
  el contador en 10, no diez renglones. Revisas una vez.</p>
</div>

<h2>Las tres decisiones</h2>

<h3>Crear producto</h3>
<p>Úsalo cuando el artículo <strong>de verdad es nuevo</strong>. Da de alta el producto con
la descripción del proveedor, la categoría y el tipo que estén configurados, guarda el
costo según la política, y de paso registra el código del proveedor.</p>

<h3>Ligar</h3>
<p>Úsalo cuando el artículo <strong>ya lo tienes</strong>, nada más que el proveedor le
llama distinto. Elige el producto en la columna <em>Producto</em> y presiona
<strong>Ligar</strong>. Esto es lo más valioso que puedes hacer: le estás enseñando la
equivalencia y ya no te vuelve a preguntar.</p>

<h3>Descartar</h3>
<p>Para lo que no es un producto: fletes, anticipos, redondeos, notas de crédito, servicios
sueltos. Se guarda como descartado y deja de aparecer en la lista de pendientes.</p>

<h2>Lo que pasa después de decidir</h2>
<p>Al crear o ligar, la aplicación <strong>regresa a las facturas en borrador</strong> donde
apareció ese artículo y les pone el producto en el renglón. No tienes que ir a buscarlas
una por una.</p>

<div class="alert alert-warning">
  <p>Solo toca facturas <strong>en borrador</strong>. Una factura ya publicada no se
  modifica: si necesitas corregirla, hay que pasarla a borrador a mano.</p>
</div>

<h2>Cómo trabajar rápido</h2>
<ul>
  <li>Ordena por <strong>Visto</strong> de mayor a menor: lo que más se repite es lo que más
      te conviene resolver primero.</li>
  <li>Agrupa por <strong>Proveedor</strong> para revisar de un jalón todo lo de un mismo
      surtidor.</li>
  <li>Puedes usar los botones directamente desde la lista, sin abrir cada renglón.</li>
  <li>Si te equivocaste, abre el renglón y usa <strong>Regresar a revisión</strong>.</li>
</ul>
""",
    },
    {
        "icon": "\U0001F517",  # 🔗
        "name_en": "3. The vendor codes (how it learns)",
        "name_es": "3. Los códigos de proveedor (así aprende)",
        "body_en": """
<p>This is the piece that keeps the work from repeating, and it is worth understanding.</p>

<h2>The problem</h2>
<p>Your vendor prints <strong>their</strong> code on the invoice, say
<code>TXB-PNT-32</code>. In your catalogue you have the same item as
<em>Denim trousers, ladies', size 32</em>, with your own reference. Odoo, on its own,
compares the vendor's code against yours, and since they almost never match, it recognises
nothing.</p>

<h2>The solution</h2>
<p>Every time you create or link a product from a proposal, the application stores that
match:</p>

<table class="table table-bordered">
  <thead>
    <tr><th>What the vendor says</th><th>Your product</th></tr>
  </thead>
  <tbody>
    <tr><td><code>TXB-PNT-32</code></td><td>Denim trousers, ladies', size 32</td></tr>
    <tr><td><code>NRM-AUD-BT</code></td><td>Black bluetooth headphones</td></tr>
  </tbody>
</table>

<p>From then on, any future bill from <em>that</em> vendor with that code matches on its
own, without going through the review inbox.</p>

<div class="alert alert-info">
  <p>The match is <strong>per vendor</strong>. Two vendors using the same code for
  different things causes no confusion.</p>
</div>

<h2>Where to see and fix it</h2>
<p><em>Accounting &#9656; Vendors &#9656; Vendor Codes</em>. The whole table is there and
you can edit it straight in the list:</p>
<ul>
  <li><strong>Vendor code</strong> — the code they use.</li>
  <li><strong>Vendor name</strong> — what they call it on their invoice.</li>
  <li><strong>Product</strong> — yours.</li>
  <li><strong>From a bill</strong> — ticked when the price was taken from an imported bill.
      It is the flag the <em>&laquo;only the first time&raquo;</em> cost policy relies
      on.</li>
</ul>

<h2>Getting ahead of the work</h2>
<p>You do not have to wait for a bill. If you already have a vendor's list of codes at
hand, you can capture them here from the start and the first bill they send will match in
full.</p>

<h3>If it matched the wrong product</h3>
<p>Find the vendor code on this screen, fix the product, done. The next bill uses the right
one. The bill that got it wrong does have to be fixed by hand if it is already posted.</p>
""",
        "body_es": """
<p>Ésta es la pieza que hace que el trabajo no se repita, y vale la pena entenderla.</p>

<h2>El problema</h2>
<p>Tu proveedor imprime en su factura <strong>su</strong> clave, por ejemplo
<code>TXB-PNT-32</code>. Tú en tu catálogo tienes el mismo artículo como
<em>Pantalón mezclilla dama T32</em>, con tu propia referencia. Odoo, por sí solo, compara
la clave del proveedor contra la tuya, y como casi nunca coinciden, no reconoce nada.</p>

<h2>La solución</h2>
<p>Cada vez que creas o ligas un producto desde una propuesta, la aplicación guarda esa
equivalencia:</p>

<table class="table table-bordered">
  <thead>
    <tr><th>Lo que dice el proveedor</th><th>Tu producto</th></tr>
  </thead>
  <tbody>
    <tr><td><code>TXB-PNT-32</code></td><td>Pantalón mezclilla dama T32</td></tr>
    <tr><td><code>NRM-AUD-BT</code></td><td>Audífonos bluetooth negros</td></tr>
  </tbody>
</table>

<p>A partir de ahí, cualquier factura futura de <em>ese</em> proveedor con esa clave
empareja sola, sin pasar por la bandeja de revisión.</p>

<div class="alert alert-info">
  <p>La equivalencia es <strong>por proveedor</strong>. Que dos proveedores usen la misma
  clave para cosas distintas no causa ningún enredo.</p>
</div>

<h2>Dónde verla y corregirla</h2>
<p><em>Contabilidad ▸ Proveedores ▸ Códigos de proveedor</em>. Ahí está la tabla completa y
la puedes editar directo en la lista:</p>
<ul>
  <li><strong>Código del proveedor</strong> — la clave que él usa.</li>
  <li><strong>Nombre en el proveedor</strong> — cómo le llama en su factura.</li>
  <li><strong>Producto</strong> — el tuyo.</li>
  <li><strong>De una factura</strong> — palomeado cuando el precio se tomó de una factura
      importada. Es el dato en el que se apoya la política de costo
      <em>«solo la primera vez»</em>.</li>
</ul>

<h2>Adelantarte al trabajo</h2>
<p>No hace falta esperar a que llegue una factura. Si ya tienes a la mano la lista de
claves de un proveedor, puedes capturarlas aquí desde el principio y la primera factura
que mande va a emparejar completa.</p>

<h3>Si emparejó el producto equivocado</h3>
<p>Busca en esta pantalla el código del proveedor, corrige el producto, y listo. La
siguiente factura ya usa el correcto. La factura que se equivocó sí hay que corregirla a
mano si ya está publicada.</p>
""",
    },
    {
        "icon": "\U0001F4B2",  # 💲
        "name_en": "4. The cost: who's in charge",
        "name_es": "4. El costo: quién manda",
        "body_en": """
<p>This is the part worth deciding <strong>once</strong>, with whoever keeps the books, and
never touching again.</p>

<h2>The three options</h2>
<table class="table table-bordered">
  <tbody>
    <tr>
      <td style="width:24%"><strong>Never</strong></td>
      <td>The bill price is only informative. You control your products' cost by hand.</td>
    </tr>
    <tr>
      <td><strong>Only the first time</strong><br/><span class="text-muted">(this is how it is set)</span></td>
      <td>The cost is saved the first time the product is linked with that vendor, and never
          moves again. It is the calmest option: purchase prices go up and down without
          dragging your valuation.</td>
    </tr>
    <tr>
      <td><strong>Always</strong></td>
      <td>Every bill updates the vendor price and the cost. Useful if you want the cost to
          always reflect the latest you paid.</td>
    </tr>
  </tbody>
</table>

<h2>What exactly gets written</h2>
<ul>
  <li>The <strong>vendor price</strong> is stored in the bill's currency, on the
      <em>Vendor Codes</em> screen.</li>
  <li>The <strong>product cost</strong> is converted to the company currency before being
      saved.</li>
  <li>The price used is the one <strong>already with the discount applied</strong>, which
      is what you actually paid.</li>
  <li>A line with a zero price (a sample, a bonus) touches nothing.</li>
</ul>

<div class="alert alert-warning">
  <p><strong>Accounting safeguard.</strong> The product cost is only written when the
  costing method is <em>Standard Price</em>. If a product uses automated costing (FIFO or
  average), the application <strong>does not touch it</strong>, so as not to generate
  revaluation entries on its own.</p>
</div>

<h2>Sale price</h2>
<p>There is an optional <strong>margin</strong> in the settings. Set it to, say, 60, and
every new product created from a bill is born with a sale price 60% above cost. At zero,
the sale price stays at zero and you set it yourself.</p>
""",
        "body_es": """
<p>Ésta es la parte que conviene decidir <strong>una vez</strong>, con la persona que lleva
la contabilidad, y no volver a tocar.</p>

<h2>Las tres opciones</h2>
<table class="table table-bordered">
  <tbody>
    <tr>
      <td style="width:24%"><strong>Nunca</strong></td>
      <td>El precio de la factura es solo informativo. El costo de tus productos lo
          controlas tú a mano.</td>
    </tr>
    <tr>
      <td><strong>Solo la primera vez</strong><br/><span class="text-muted">(así está configurado)</span></td>
      <td>El costo se guarda la primera vez que se liga el producto con ese proveedor, y ya
          no se vuelve a mover. Es lo más tranquilo: los precios de compra suben y bajan sin
          arrastrar tu valuación.</td>
    </tr>
    <tr>
      <td><strong>Siempre</strong></td>
      <td>Cada factura actualiza el precio del proveedor y el costo. Útil si quieres que el
          costo refleje siempre lo último que pagaste.</td>
    </tr>
  </tbody>
</table>

<h2>Qué se escribe exactamente</h2>
<ul>
  <li>El <strong>precio del proveedor</strong> se guarda en la moneda de la factura, en la
      pantalla de <em>Códigos de proveedor</em>.</li>
  <li>El <strong>costo del producto</strong> se convierte a la moneda de la empresa antes de
      guardarse.</li>
  <li>Se usa el precio <strong>ya con el descuento aplicado</strong>, que es lo que
      realmente pagaste.</li>
  <li>Un renglón con precio en cero (una muestra, una bonificación) no toca nada.</li>
</ul>

<div class="alert alert-warning">
  <p><strong>Salvaguarda contable.</strong> El costo del producto solo se escribe cuando el
  método de costeo es <em>Precio estándar</em>. Si un producto usa costeo automático
  (FIFO o promedio), la aplicación <strong>no lo toca</strong>, para no generar asientos de
  revaluación por su cuenta.</p>
</div>

<h2>Precio de venta</h2>
<p>Existe un <strong>margen</strong> opcional en la configuración. Si lo pones en, digamos,
60, cada producto nuevo creado desde una factura nace con un precio de venta 60% arriba del
costo. En cero, el precio de venta se queda en cero y lo pones tú.</p>
""",
    },
    {
        "icon": "\U0001F5BC️",  # 🖼️
        "name_en": "5. Product images",
        "name_es": "5. Las fotos de producto",
        "body_en": """
<p>A catalogue built from bills is born without pictures. The application can look for
them.</p>

<h2>The three modes</h2>
<ul>
  <li><strong>Disabled</strong> — it looks for nothing.</li>
  <li><strong>Propose candidates</strong> — it brings several pictures per product and you
      choose. The recommended option.</li>
  <li><strong>Attach the best match</strong> — it takes the first valid one without asking.
      Fast, but wrong now and then.</li>
</ul>

<h2>How to choose a picture</h2>
<ol>
  <li>Open the row in <em>Proposed Products</em>.</li>
  <li>Go to the <strong>Image candidates</strong> tab. Each card shows the picture, its
      size in pixels and the site it came from.</li>
  <li>Press <strong>Use this one</strong> on the right one. When the product is created,
      the picture goes with it.</li>
</ol>

<p>If none is good, the <strong>Look for images</strong> button tries again. It helps most
after you fix the description: the search uses the line text, so a better description gives
better pictures.</p>

<div class="alert alert-info">
  <p><strong>The search does not make you wait.</strong> It runs on its own every half
  hour, never while a bill is being imported. If you have just imported and do not see
  pictures yet, give it a few minutes or use the button to force them.</p>
</div>

<h2>One tip that actually changes the result</h2>
<p>Vendor descriptions come abbreviated and sometimes misspelled, and that confuses the
search. If an item is called <em>&laquo;BLK MESH LADIES&raquo;</em> and is really a
<em>mesh fabric</em>, the search will bring back anything. Fix the description before
searching.</p>

<div class="alert alert-warning">
  <p><strong>You are responsible for the images.</strong> Pictures come from the internet
  and may have an owner. Before publishing a product on the online store, check that the
  picture can be used, or replace it with your own. The application helps you find
  candidates; the decision is the company's.</p>
</div>
""",
        "body_es": """
<p>Un catálogo armado a partir de facturas nace sin fotos. La aplicación puede buscarlas.</p>

<h2>Los tres modos</h2>
<ul>
  <li><strong>Desactivado</strong> — no busca nada.</li>
  <li><strong>Proponer candidatas</strong> — trae varias fotos por producto y tú eliges.
      Es lo recomendable.</li>
  <li><strong>Adjuntar la mejor coincidencia</strong> — toma la primera válida sin
      preguntar. Rápido, pero de vez en cuando se equivoca.</li>
</ul>

<h2>Cómo elegir una foto</h2>
<ol>
  <li>Abre el renglón en <em>Productos propuestos</em>.</li>
  <li>Ve a la pestaña <strong>Imágenes candidatas</strong>. Cada tarjeta muestra la foto, su
      tamaño en píxeles y el sitio de donde salió.</li>
  <li>Presiona <strong>Usar ésta</strong> en la que corresponda. Al crear el producto, la
      foto se va con él.</li>
</ol>

<p>Si ninguna sirve, el botón <strong>Buscar imágenes</strong> vuelve a intentar. Sirve
sobre todo después de corregir la descripción: la búsqueda usa el texto del renglón, así
que una descripción mejor da mejores fotos.</p>

<div class="alert alert-info">
  <p><strong>La búsqueda no te hace esperar.</strong> Corre por su cuenta cada media hora,
  nunca mientras se importa una factura. Si acabas de importar y todavía no ves fotos, dales
  unos minutos o usa el botón para forzarlas.</p>
</div>

<h2>Un consejo que sí cambia el resultado</h2>
<p>Las descripciones de los proveedores vienen abreviadas y a veces mal escritas, y eso
confunde al buscador. Si un artículo se llama <em>«MAYA NEGRA DAMA»</em> y en realidad es
una <em>malla</em>, la búsqueda va a traer cualquier cosa. Corrige la descripción antes de
buscar.</p>

<div class="alert alert-warning">
  <p><strong>Responsabilidad sobre las imágenes.</strong> Las fotos vienen de internet y
  pueden tener dueño. Antes de publicar un producto en la tienda en línea, revisa que la
  foto se pueda usar, o cámbiala por una tuya. La aplicación te ayuda a encontrar
  candidatas; la decisión es de la empresa.</p>
</div>
""",
    },
    {
        "icon": "⚙️",  # ⚙️
        "name_en": "6. Configuration (administrator)",
        "name_es": "6. Configuración (administrador)",
        "body_en": """
<p>Everything lives in <em>Accounting &#9656; Configuration &#9656; Settings</em>, in the
<strong>Products from Vendor Bills</strong> block. The settings are
<strong>per company</strong>.</p>

<h2>Unknown products</h2>
<table class="table table-bordered">
  <tbody>
    <tr><td style="width:30%"><strong>Disabled</strong></td>
        <td>The application stays quiet; Odoo behaves as it does out of the box.</td></tr>
    <tr><td><strong>Propose for review</strong></td>
        <td>The unknown waits for your approval. <em>This is the option set today.</em></td></tr>
    <tr><td><strong>Create automatically</strong></td>
        <td>The product is born during the import, without asking. Only makes sense with
            very trusted vendors and very clean catalogues.</td></tr>
  </tbody>
</table>

<p>Alongside that you configure how new products are born:</p>
<ul>
  <li><strong>Type</strong> — Goods or Service.</li>
  <li><strong>Category</strong> — empty uses Odoo's default category. Better to point it at
      a category of your own, something like <em>&laquo;To classify&raquo;</em>, to find
      them later.</li>
  <li><strong>Track inventory</strong> — leave it on if you want the product to move stock.
      A product created without this flag <strong>never</strong> affects inventory, and
      that shows up late.</li>
  <li><strong>Standard item identifier as barcode</strong> — if the XML carries a GTIN/EAN
      and no other product uses it, it is set as the barcode.</li>
  <li><strong>Vendor code as internal reference</strong> — off on purpose: the vendor code
      is theirs, not yours, and two vendors may reuse it. Either way it is always stored in
      the lookup table.</li>
</ul>

<h2>Cost from the bill</h2>
<p>Never / Only the first time / Always, plus the <strong>Also update the product
cost</strong> checkbox and the <strong>Sale price margin</strong>. Explained in the section
<em>&laquo;The cost: who's in charge&raquo;</em>.</p>

<h2>Product images</h2>
<ul>
  <li><strong>Search engine</strong> — <em>DuckDuckGo</em> needs no key and is what is in
      use. <em>Google Programmable Search</em> is an alternative if the company already pays
      for a key.</li>
  <li><strong>Candidates per product</strong> — how many pictures to bring. Four or six is
      fine; more only slows the review.</li>
  <li><strong>Minimum side</strong> — discards tiny pictures. 400 px is a good floor.</li>
  <li><strong>Add to every search</strong> — text appended to each search to steer it.
      Useful if you sell a very specific line.</li>
</ul>

<h2>Permissions</h2>
<p>Whoever has access to <em>Invoicing</em> can review and apply proposals. Deleting them
needs an <em>Accountant</em> profile.</p>

<h2>The scheduled action</h2>
<p>The image search runs under <em>Settings &#9656; Technical &#9656; Scheduled
Actions</em>, named <em>&laquo;Vendor bill products: look for product images&raquo;</em>,
every 30 minutes. If images are disabled, it does nothing.</p>
""",
        "body_es": """
<p>Todo vive en <em>Contabilidad ▸ Configuración ▸ Ajustes</em>, en el bloque
<strong>Productos desde facturas de proveedor</strong>. Los ajustes son
<strong>por compañía</strong>.</p>

<h2>Productos desconocidos</h2>
<table class="table table-bordered">
  <tbody>
    <tr><td style="width:30%"><strong>Desactivado</strong></td>
        <td>La aplicación se queda quieta; Odoo se comporta como de fábrica.</td></tr>
    <tr><td><strong>Proponer para revisión</strong></td>
        <td>Lo desconocido espera tu visto bueno. <em>Es la opción configurada hoy.</em></td></tr>
    <tr><td><strong>Crear automáticamente</strong></td>
        <td>El producto nace durante la importación, sin preguntar. Solo tiene sentido con
            proveedores muy confiables y catálogos muy limpios.</td></tr>
  </tbody>
</table>

<p>Junto a eso se configura cómo nacen los productos nuevos:</p>
<ul>
  <li><strong>Tipo</strong> — Bienes o Servicio.</li>
  <li><strong>Categoría</strong> — vacío usa la categoría por omisión de Odoo. Conviene
      apuntarla a una categoría propia, tipo <em>«Por clasificar»</em>, para localizarlos
      después.</li>
  <li><strong>Controlar inventario</strong> — déjalo encendido si quieres que el producto
      mueva existencias. Un producto creado sin esta marca <strong>nunca</strong> afecta el
      inventario, y eso se nota tarde.</li>
  <li><strong>Identificador estándar como código de barras</strong> — si el XML trae un
      GTIN/EAN y no lo usa otro producto, se pone como código de barras.</li>
  <li><strong>Código del proveedor como referencia interna</strong> — apagado a propósito:
      el código del proveedor es suyo, no tuyo, y dos proveedores pueden repetirlo. De todos
      modos siempre se guarda en la tabla de equivalencias.</li>
</ul>

<h2>Costo desde la factura</h2>
<p>Nunca / Solo la primera vez / Siempre, más la casilla <strong>Actualizar también el
costo del producto</strong> y el <strong>margen de precio de venta</strong>. Está explicado
en la sección <em>«El costo: quién manda»</em>.</p>

<h2>Imágenes de producto</h2>
<ul>
  <li><strong>Buscador</strong> — <em>DuckDuckGo</em> no necesita ninguna llave y es lo que
      está en uso. <em>Google Programmable Search</em> es una alternativa si la empresa ya
      paga una llave.</li>
  <li><strong>Candidatas por producto</strong> — cuántas fotos traer. Cuatro o seis está
      bien; más solo alenta la revisión.</li>
  <li><strong>Lado mínimo</strong> — descarta fotos chicas. 400 px es un buen piso.</li>
  <li><strong>Agregar a toda búsqueda</strong> — texto que se suma a cada búsqueda para
      dirigirla. Útil si vendes un giro muy específico.</li>
</ul>

<h2>Permisos</h2>
<p>Quien tenga acceso a <em>Facturación</em> puede revisar y aplicar propuestas. Borrarlas
requiere perfil de <em>Contador</em>.</p>

<h2>La tarea programada</h2>
<p>La búsqueda de fotos corre en <em>Ajustes ▸ Técnico ▸ Acciones planificadas</em>, bajo el
nombre <em>«Productos desde facturas: buscar imágenes de producto»</em>, cada 30 minutos.
Si las imágenes están desactivadas, no hace nada.</p>
""",
    },
    {
        "icon": "\U0001F527",  # 🔧
        "name_en": "7. If something didn't go as expected",
        "name_es": "7. Si algo no salió como esperabas",
        "body_en": """
<h2>I imported a bill and no proposal appeared</h2>
<ul>
  <li>Check that the bill filled itself. If you captured the lines by hand, the application
      does not step in: it only works on what comes in the file.</li>
  <li>It may be that <strong>everything matched</strong>, which is the goal. Open it and see
      whether the lines already carry a product.</li>
  <li>Check in Settings that the mode is not <strong>Disabled</strong>.</li>
</ul>

<h2>It matched the wrong product</h2>
<ol>
  <li>Go to <em>Vendor Codes</em>, find the code and fix the product.</li>
  <li>Fix that bill's line by hand (if it is already posted, set it back to draft first).</li>
</ol>
<p>From then on it uses the right one.</p>

<h2>The cost was not updated</h2>
<p>In order of likelihood:</p>
<ol>
  <li>The policy is <strong>Only the first time</strong> and that product already had it
      recorded. That is the correct behaviour.</li>
  <li>The product uses <strong>FIFO or average</strong> costing. The application does not
      touch it on purpose, so as not to meddle with the valuation.</li>
  <li>The <em>Also update the product cost</em> checkbox is off. In that case the vendor
      price is still saved, but not the cost.</li>
</ol>

<h2>The line ended up with no product and no description</h2>
<p>It should not happen: the application fills in the XML description when it finds no
product. If a completely blank line appears, it is a case worth reporting with the XML on
hand.</p>

<h2>It found no picture</h2>
<ul>
  <li>Fix the description and press <strong>Look for images</strong> again. That helps the
      most.</li>
  <li>Lower the <strong>minimum side</strong> in Settings if the item is so specific that
      only small pictures exist.</li>
  <li>If <em>no</em> product finds pictures, the server is probably not reaching the
      internet. That one is for support.</li>
</ul>

<h2>I rejected something by mistake</h2>
<p>Remove the <strong>&laquo;To review&raquo;</strong> filter, find the row under
<strong>&laquo;Rejected&raquo;</strong>, open it and press <strong>Back to
review</strong>.</p>

<h2>Proposals show up for things that are not products</h2>
<p>Freight, down payments and roundings will keep arriving because the vendor bills them as
one more line. Reject them: each is rejected once and never bothers you again, even if it
keeps arriving on new bills.</p>

<hr/>
<p class="text-muted">Support: <strong>soporte@xubax.com</strong></p>
""",
        "body_es": """
<h2>Importé una factura y no apareció ninguna propuesta</h2>
<ul>
  <li>Revisa que la factura se haya llenado sola. Si los renglones los capturaste a mano, la
      aplicación no interviene: solo trabaja sobre lo que viene en el archivo.</li>
  <li>Puede que <strong>todo haya emparejado</strong>, que es la meta. Ábrela y fíjate si
      los renglones ya traen producto.</li>
  <li>Verifica en Ajustes que el modo no esté en <strong>Desactivado</strong>.</li>
</ul>

<h2>Emparejó con el producto equivocado</h2>
<ol>
  <li>Ve a <em>Códigos de proveedor</em>, busca el código y corrige el producto.</li>
  <li>Corrige el renglón de esa factura a mano (si ya está publicada, pásala a borrador
      primero).</li>
</ol>
<p>De ahí en adelante ya usa el correcto.</p>

<h2>El costo no se actualizó</h2>
<p>Por orden de probabilidad:</p>
<ol>
  <li>La política está en <strong>Solo la primera vez</strong> y ese producto ya lo tenía
      registrado. Es el comportamiento correcto.</li>
  <li>El producto usa costeo <strong>FIFO o promedio</strong>. La aplicación no lo toca a
      propósito, para no meterse con la valuación.</li>
  <li>La casilla <em>Actualizar también el costo del producto</em> está apagada. En ese caso
      sí se guarda el precio del proveedor, pero no el costo.</li>
</ol>

<h2>El renglón quedó sin producto y sin descripción</h2>
<p>No debería pasar: la aplicación rellena la descripción del XML cuando no encuentra
producto. Si aparece un renglón totalmente vacío, es un caso que vale la pena reportar con
el XML a la mano.</p>

<h2>No encontró ninguna foto</h2>
<ul>
  <li>Corrige la descripción y presiona <strong>Buscar imágenes</strong> otra vez. Es lo que
      más ayuda.</li>
  <li>Baja el <strong>lado mínimo</strong> en Ajustes si el artículo es tan específico que
      solo hay fotos chicas.</li>
  <li>Si <em>ningún</em> producto encuentra fotos, seguramente el servidor no está saliendo
      a internet. Eso es para soporte.</li>
</ul>

<h2>Descarté algo por error</h2>
<p>Quita el filtro <strong>«Por revisar»</strong>, busca el renglón en
<strong>«Descartado»</strong>, ábrelo y presiona <strong>Regresar a revisión</strong>.</p>

<h2>Aparecen propuestas de cosas que no son productos</h2>
<p>Fletes, anticipos y redondeos van a seguir llegando porque el proveedor los factura como
un renglón más. Descártalos: cada uno se descarta una sola vez y ya no vuelve a molestar,
aunque siga llegando en facturas nuevas.</p>

<hr/>
<p class="text-muted">Soporte: <strong>soporte@xubax.com</strong></p>
""",
    },
]
