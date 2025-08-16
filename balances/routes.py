from flask import Blueprint, render_template, redirect, url_for, request
from app import client
from foundry_sdk_runtime.types import BatchActionConfig, ReturnEditsMode, ActionConfig, ActionMode, SyncApplyActionResponse
from mr_split_sdk.ontology.action_types import DeleteResponsibilityMappingBatchRequest, DeleteSettlementsBatchRequest, EditResponsibilityMappingBatchRequest
from balances.utils import compute_balances, new_settlement_id, dollars_to_cents
from datetime import date


balances_bp = Blueprint('balances', __name__, url_prefix='/balances')

@balances_bp.route("/", methods=["GET"])
def show_balance_summary():
    responsibility_mappings = list(client.ontology.objects.ResponsibilityMapping.iterate())
    users = list(client.ontology.objects.Users.iterate())
    user_id_to_name = {u.user_id: u.full_name for u in users if u.user_id and u.full_name}

    purchased_items = list(client.ontology.objects.PurchasedItem.iterate())
    line_id_to_item = {item.line_id: item for item in purchased_items if item.line_id}

    # Build participants per line for fair split math
    from collections import defaultdict
    line_to_users = defaultdict(list)
    for rm in responsibility_mappings:
        if rm.line_id and rm.user_id:
            line_to_users[rm.line_id].append(rm.user_id)

    def fmt_cents(c): return f"${c/100:.2f}"
    def is_paid(status) -> bool:
        return (status or "").strip().lower() == "paid"

    # ---- display table (UNPAID only) ----
    mappings_expanded = []
    for mapping in responsibility_mappings:
        # hide rows already marked paid
        if is_paid(getattr(mapping, "status", None)):
            continue

        item = line_id_to_item.get(mapping.line_id)
        if not item or item.price is None:
            continue

        participants = line_to_users.get(mapping.line_id, [])
        n = len(participants) or 1
        price_cents = dollars_to_cents(item.price)

        base = price_cents // n
        residue = price_cents - base * n

        payer_id = item.paid_by
        share_cents = base + (residue if mapping.user_id == payer_id else 0)
        owed_cents = 0 if mapping.user_id == payer_id else share_cents

        # If someone is the payer (owes 0) we also hide the row
        if owed_cents <= 0:
            continue

        user_name = user_id_to_name.get(mapping.user_id, f"User ID {mapping.user_id}")
        paid_by_name = user_id_to_name.get(payer_id, f"User ID {payer_id}")

        mappings_expanded.append({
            "line_id": mapping.line_id,
            "receipt_id": item.receipt_id,
            "item_name": item.item_name,
            "share": fmt_cents(owed_cents),
            "user_name": user_name,
            "status": mapping.status,
            "paid_by": paid_by_name
        })

    mappings_expanded.sort(key=lambda x: (x["line_id"], x["user_name"]))

    # keep balances logic as-is (it already respects settlements)
    settlements = list(client.ontology.objects.Settlements.iterate())
    pairwise, per_user = compute_balances(responsibility_mappings, purchased_items, settlements)

    pairwise_display = [{
        "from_id": frm,
        "to_id":   to,
        "from":    user_id_to_name.get(frm, f"User ID {frm}"),
        "to":      user_id_to_name.get(to,  f"User ID {to}"),
        "amount_cents": amt,
        "amount": fmt_cents(amt),
    } for (frm, to, amt) in pairwise]

    per_user_display = [{
        "user":  user_id_to_name.get(uid, f"User ID {uid}"),
        "net":   fmt_cents(cents),
        "status": "is owed" if cents > 0 else ("owes" if cents < 0 else "settled")
    } for uid, cents in sorted(per_user.items(), key=lambda kv: user_id_to_name.get(kv[0], str(kv[0])) or "")]

    error = request.args.get("error")

    return render_template(
        "balances.html",
        mappings=mappings_expanded,   # unpaid rows only
        pairwise=pairwise_display,
        per_user=per_user_display,
        error=error
    )



@balances_bp.route("/delete_all", methods=["POST"])
def delete_all_mappings():
    # Server-side safety: require exact "DELETE" confirmation
    confirm_text = request.form.get("confirm_text", "")
    if confirm_text != "DELETE":
        return redirect(url_for("balances.show_balance_summary",
                                error="Deletion cancelled. You must type DELETE to confirm."))

    responsibility_mappings = list(client.ontology.objects.ResponsibilityMapping.iterate())

    if responsibility_mappings:
        requests = [
            DeleteResponsibilityMappingBatchRequest(
                responsibility_mapping=mapping.mapping_id  # primary key field
            )
            for mapping in responsibility_mappings
        ]
        if len(requests) > 0:
            client.ontology.batch_actions.delete_responsibility_mapping(
                batch_action_config=BatchActionConfig(return_edits=ReturnEditsMode.ALL),
                requests=requests
            )

    return redirect(url_for("balances.show_balance_summary"))


@balances_bp.route("/settle", methods=["POST"])
def settle_debt():
    if request.form.get("confirm_text", "") != "CONFIRM":
        return redirect(url_for("balances.show_balance_summary",
                                error="Settlement cancelled. Type CONFIRM to proceed."))

    try:
        from_user_id = int(request.form["from_user_id"])
        to_user_id   = int(request.form["to_user_id"])
        amount_cents = int(request.form.get("amount_cents", "0"))
        note         = "test"

        if amount_cents <= 0:
            return redirect(url_for("balances.show_balance_summary",
                                    error="Invalid settlement amount."))

        # 1) Record the settlement
        created = date.today()
        response: SyncApplyActionResponse = client.ontology.actions.create_settlements(
            action_config=ActionConfig(
                mode=ActionMode.VALIDATE_AND_EXECUTE,
                return_edits=ReturnEditsMode.ALL
            ),
            settlement_id=new_settlement_id(),
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            amount_cents=amount_cents,
            created_at=created,
            note=note
        )

        if response.validation.result != "VALID":
            return redirect(url_for("balances.show_balance_summary",
                                    error="Settlement validation failed."))

        # 2) Mark BOTH directions of responsibility mappings as 'paid'
        purchased_items = list(client.ontology.objects.PurchasedItem.iterate())
        line_id_to_item = {it.line_id: it for it in purchased_items if getattr(it, "line_id", None) is not None}

        responsibility_mappings = list(client.ontology.objects.ResponsibilityMapping.iterate())

        edits = []
        for rm in responsibility_mappings:
            lid = getattr(rm, "line_id", None)
            uid = getattr(rm, "user_id", None)
            mid = getattr(rm, "mapping_id", None)

            if lid is None or uid is None or mid is None:
                continue

            item = line_id_to_item.get(lid)
            if not item:
                continue

            payer = getattr(item, "paid_by", None)
            # direction A->B or B->A
            should_mark_paid = (
                (uid == from_user_id and payer == to_user_id) or
                (uid == to_user_id   and payer == from_user_id)
            )

            if should_mark_paid:
                # Only update if not already 'paid'
                current_status = (getattr(rm, "status", "") or "").strip().lower()
                if current_status != "paid":
                    edits.append(
                        EditResponsibilityMappingBatchRequest(
                            responsibility_mapping=mid,
                            line_id=lid,
                            user_id=uid,
                            status="paid"
                        )
                    )

        if edits:
            client.ontology.batch_actions.edit_responsibility_mapping(
                batch_action_config=BatchActionConfig(return_edits=ReturnEditsMode.ALL),
                requests=edits
            )

        return redirect(url_for("balances.show_balance_summary"))

    except ValueError:
        return redirect(url_for("balances.show_balance_summary",
                                error="Bad form values for settlement."))
    except Exception as e:
        return redirect(url_for("balances.show_balance_summary",
                                error=f"Failed to record settlement: {e}"))


@balances_bp.route("/delete_all_settlements", methods=["POST"])
def delete_all_settlements():
    confirm_text = request.form.get("confirm_text", "")
    if confirm_text != "DELETE":
        return redirect(url_for("balances.show_balance_summary",
                                error="Deletion cancelled. You must type DELETE to confirm."))

    settlements = list(client.ontology.objects.Settlements.iterate())

    if settlements:
        requests = [
            DeleteSettlementsBatchRequest(
                settlements=s.settlement_id  # primary key field
            )
            for s in settlements
        ]
        if requests:
            client.ontology.batch_actions.delete_settlements(
                batch_action_config=BatchActionConfig(return_edits=ReturnEditsMode.ALL),
                requests=requests
            )

    return redirect(url_for("balances.show_balance_summary"))