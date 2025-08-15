from mr_split_sdk.ontology.objects import Users, Settlements
from app import client
from collections import defaultdict
from decimal import Decimal
from datetime import datetime


def new_settlement_id() -> int:
    # Query for the user with the highest settlement_id
    highest_settlement = next(
        client.ontology.objects.Settlements
        .order_by(Settlements.object_type.settlement_id.desc())
        .iterate(),
        None  # default if none found
    )

    if highest_settlement is None or highest_settlement.settlement_id is None:
        return 1  # no users, start at 1

    return highest_settlement.settlement_id + 1

def dollars_to_cents(val) -> int:
    if val is None: return 0
    return int((Decimal(str(val)) * 100).quantize(Decimal("1")))

def compute_balances(responsibility_mappings, purchased_items, settlements=None):
    settlements = settlements or []
    line_to_item = {it.line_id: it for it in purchased_items if it.line_id}
    line_to_users = defaultdict(list)
    for m in responsibility_mappings:
        if m.line_id and m.user_id:
            line_to_users[m.line_id].append(m.user_id)

    # raw debts (u -> payer) before settlements
    debts = defaultdict(int)

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
        residue = price_cents - base * n
        for u in users:
            share = base + (residue if u == payer else 0)
            if u != payer and share > 0:
                debts[(u, payer)] += share

    # apply settlements: subtract payments from the matching direction
    paid = defaultdict(int)  # (from, to) -> cents paid
    for s in settlements:
        paid[(s.from_user_id, s.to_user_id)] += s.amount_cents

    for key, amt_paid in paid.items():
        owed = debts.get(key, 0)
        if amt_paid >= owed:
            debts[key] = 0
        else:
            debts[key] = owed - amt_paid

    # pairwise netting
    net_signed = defaultdict(int)  # (min, max) -> signed cents
    for (u, v), amt in debts.items():
        if amt == 0: continue
        key = (u, v) if u < v else (v, u)
        sign = 1 if u < v else -1
        net_signed[key] += sign * amt

    pairwise = []
    for (a, b), signed in net_signed.items():
        if signed > 0:   pairwise.append((a, b, signed))     # a owes b
        elif signed < 0: pairwise.append((b, a, -signed))    # b owes a

    per_user = defaultdict(int)
    for frm, to, amt in pairwise:
        per_user[frm] -= amt
        per_user[to]  += amt

    return pairwise, per_user
