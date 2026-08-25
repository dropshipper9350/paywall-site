"""Direct UPI payments — no gateway, no fees, no KYC.

There is no callback from a raw UPI QR/VPA payment: money moves
peer-to-peer between UPI apps and never touches your server, so
nothing here can auto-confirm a payment. Instead:

  1. We show a QR code (and a mobile deep link) that opens the
     buyer's UPI app with your VPA, the amount, and a note prefilled.
  2. The buyer pays, then submits the UPI transaction reference
     (UTR / Ref No) shown in their app after paying.
  3. You check that reference against your own bank/UPI app and
     approve it from /admin — that's what actually grants access.

If you later want this to unlock automatically, that requires either
a payment aggregator (Razorpay, Cashfree, etc.) or a business current
account with bank UPI API access — both are effectively a gateway
relationship, just with different fees/setup than Razorpay.
"""
import base64
import io
import os
import time
import urllib.parse

import qrcode


def upi_uri(amount_rupees, note, order_ref):
    vpa = os.environ.get("UPI_VPA", "your-vpa@bank")
    payee_name = os.environ.get("UPI_PAYEE_NAME", "Your Name")
    params = {
        "pa": vpa,
        "pn": payee_name,
        "am": f"{amount_rupees:.2f}",
        "cu": "INR",
        "tn": note,
        "tr": order_ref,
    }
    return "upi://pay?" + urllib.parse.urlencode(params)


def qr_data_uri(uri):
    """Renders the UPI URI as a QR code and returns it as a data: URI
    so it can go straight into an <img src="..."> with no extra route."""
    img = qrcode.make(uri, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def unique_amount(base_rupees, order_id):
    """Adds a few paise derived from the order id so each pending
    order has a slightly different amount. Purely a reconciliation
    aid — lets you match a bank-statement entry to an order by
    amount alone, without depending only on a self-reported UTR."""
    extra_paise = order_id % 97  # small, effectively unique for low volume
    return base_rupees + extra_paise / 100


def new_order_ref(user_id):
    return f"UNLOCK{user_id}{int(time.time())}"
