from mr_split_sdk.ontology.objects import Users
from app import client
from collections import defaultdict
from decimal import Decimal

def new_user_id() -> int:
    # Query for the user with the highest user_id
    highest_user = next(
        client.ontology.objects.Users
        .where(~Users.object_type.full_name.is_null())
        .order_by(Users.object_type.user_id.desc())
        .iterate(),
        None  # default if none found
    )

    if highest_user is None or highest_user.user_id is None:
        return 1  # no users, start at 1

    return highest_user.user_id + 1

def dollars_to_cents(val) -> int:
    if val is None:
        return 0
    # Works for Decimal/str/float; normalize through Decimal
    return int((Decimal(str(val)) * 100).quantize(Decimal("1")))

def compute_balances(responsibility_mappings, purchased_items):
    """
    Returns:
      pairwise: list of tuples (from_user_id, to_user_id, amount_cents)
      per_user: dict user_id -> net_cents  (negative = owes; positive = is owed)
    """
    # Index items and who is responsible per line
    line_to_item = {it.line_id: it for it in purchased_items if it.line_id}
    line_to_users = defaultdict(list)
    for m in responsibility_mappings:
        if m.line_id and m.user_id:
            line_to_users[m.line_id].append(m.user_id)

    # Raw debts (u -> payer)
    debts = defaultdict(int)  # key: (from_user_id, to_user_id) -> cents

    for line_id, users in line_to_users.items():
        item = line_to_item.get(line_id)
        if not item or item.paid_by is None or item.price is None:
            continue

        payer = item.paid_by
        price_cents = dollars_to_cents(item.price)
        n = len(users)
        if n <= 0 or price_cents <= 0:
            continue

        base = price_cents // n
        residue = price_cents - base * n  # leftover cents

        # Give residue to payer so others never overpay
        for u in users:
            share = base + (residue if u == payer else 0)
            if u == payer:
                continue  # payer doesn't owe themself
            if share > 0:
                debts[(u, payer)] += share

    # Pairwise netting (compress u->v and v->u into one direction)
    net_signed = defaultdict(int)  # key: (min_id, max_id) -> signed cents
    for (u, v), amt in debts.items():
        key = (u, v) if u < v else (v, u)
        sign = 1 if u < v else -1
        net_signed[key] += sign * amt

    pairwise = []  # (from, to, amt)
    for (a, b), signed in net_signed.items():
        if signed > 0:
            pairwise.append((a, b, signed))     # a owes b
        elif signed < 0:
            pairwise.append((b, a, -signed))    # b owes a

    # Per-user net
    per_user = defaultdict(int)
    for frm, to, amt in pairwise:
        per_user[frm] -= amt
        per_user[to]  += amt

    return pairwise, per_user
