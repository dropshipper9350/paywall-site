# The Reading Room — login + UPI paywall starter

Sign up / log in, a full-site paywall, and payment straight to your
own UPI ID — no gateway, no per-transaction fee, no business KYC.

## How the payment flow actually works

A raw UPI QR code is peer-to-peer between UPI apps — it never touches
your server, so nothing can auto-confirm a payment the way a gateway
webhook would. This app does the next best thing:

1. The buyer sees a QR code (and, on mobile, a button that opens
   their UPI app directly) prefilled with your UPI ID and the price.
2. The amount is never a round number — e.g. ₹499.07, not ₹499. That's
   deliberate: it lets you match a bank-statement line to an order by
   amount alone, as a second check.
3. After paying, the buyer submits the UPI transaction reference
   (UTR) their app shows them.
4. You open **/admin** (only visible to the account whose email
   matches `ADMIN_EMAIL` in `.env`), check that reference against your
   own bank/UPI app, and click **Approve**. That's what actually
   grants access — nothing unlocks until you do.

If you'd rather have it unlock the instant someone pays, that requires
an aggregator (Razorpay, Cashfree, etc., which take a cut and need
KYC) or a business current account with bank UPI API access. This
setup trades that automation for zero fees and zero registration.

## Run it locally

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- `UPI_VPA` — your UPI ID (e.g. `yourname@oksbi`, `yourname@okhdfcbank`)
- `UPI_PAYEE_NAME` — the name buyers should see in their UPI app
- `ADMIN_EMAIL` — the email you'll sign up with to access `/admin`

```bash
python3 app.py
```

Visit `http://localhost:5000`. Sign up with the email you set as
`ADMIN_EMAIL` so that account can reach `/admin`. To test as a buyer,
sign up a second account with a different email in a private/incognito
window.

## Trying the flow end to end

1. As the buyer account, open a lesson → **Unlock full access**.
2. Scan the QR (or note the amount) and pay for real, or just note
   any string as a fake UTR to test the mechanics locally.
3. Submit that reference number.
4. Switch to the admin account, go to `/admin`, and click **Approve**.
5. Back on the buyer account, the lesson is now unlocked.

## What's in each file

- `app.py` — routes: home, article view, signup/login/logout, `/unlock` (QR + UTR form), `/admin` (approve/reject).
- `models.py` — `User` (with a `has_access` flag), `Article`, `Order` (tracks status: pending → submitted → verified/rejected).
- `payments.py` — builds the UPI deep link, renders the QR code, and computes the unique-paise amount. No external API calls at all.
- `templates/` — pages. `pay.html` has the QR/UTR-submission flow; `admin.html` is the approval queue.
- `static/css/style.css` — all styling.

## Before you launch

- Replace the three placeholder lessons (in `_seed_articles()` in `app.py`) with your real content.
- Change `SECRET_KEY` in `.env` to a real random value.
- A buyer could submit a fake or someone else's UTR — always verify against your own bank/UPI app before approving, never approve on the reference number alone.
- Check `/admin` regularly (or add yourself an email/Telegram notification later) — access only unlocks after you approve, so a slow check-in means a slow unlock for the buyer.
- Swap `sqlite:///paywall.db` for Postgres if you expect real concurrent traffic — SQLite is fine for an MVP.
- Add password-reset (not included) before sending this to real users.
