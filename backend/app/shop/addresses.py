"""A Customer's saved delivery addresses, stored per account on the server.

Every query is filtered by the signed-in Customer's user id, so two accounts that use the same browser
never see each other's addresses, and an id from another account answers 404 as if it did not exist.
The first address saved becomes the default; deleting the default makes the oldest remaining one the
default. Saving an address that matches an existing one (same pincode, house and street) updates it."""

from typing import Annotated, Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.deps import current_user, get_db
from app.db import models as m
from app.shop.routes import Delivery

router = APIRouter(prefix="/api/me/addresses")
Db = Annotated[Session, Depends(get_db)]
MAX_ADDRESSES = 20


class SavedAddress(Delivery):  # the same rules as an Order's delivery address (Kerala pincodes)
    label: Literal["Home", "Work", "Other"] = "Home"


def address_json(a: m.Address) -> dict:
    return {
        "id": a.id,
        "label": a.label,
        "default": a.is_default,
        "name": a.name,
        "house": a.house,
        "street": a.street,
        "pin": a.pin,
        "po": a.po,
        "district": a.district,
    }


def _mine(db: Session, user: m.User) -> list[m.Address]:
    return list(db.scalars(sa.select(m.Address).where(m.Address.user_id == user.id).order_by(m.Address.id)))


def _one(db: Session, user: m.User, address_id: int) -> m.Address:
    a = db.scalar(sa.select(m.Address).where(m.Address.id == address_id, m.Address.user_id == user.id))
    if a is None:
        raise HTTPException(status_code=404, detail="No such address")
    return a


def _key(house: str, street: str, pin: str) -> tuple[str, str, str]:
    return house.strip().casefold(), street.strip().casefold(), pin


def _fill(a: m.Address, body: SavedAddress, now) -> None:
    a.label, a.name, a.house, a.street = (
        body.label,
        body.name.strip(),
        body.house.strip(),
        body.street.strip(),
    )
    a.pin, a.po, a.district, a.updated_at = body.pin, body.po.strip(), body.district.strip(), now


@router.get("")
def list_addresses(request: Request, db: Db) -> list[dict]:
    return [address_json(a) for a in _mine(db, current_user(request, db))]


@router.post("", status_code=201)
def save_address(body: SavedAddress, request: Request, response: Response, db: Db) -> dict:
    user, now = current_user(request, db), request.app.state.clock.now()
    mine = _mine(db, user)
    same = next(
        (a for a in mine if _key(a.house, a.street, a.pin) == _key(body.house, body.street, body.pin)), None
    )
    if same is not None:  # the same place again (e.g. typed at checkout): update it, don't duplicate it
        _fill(same, body, now)
        db.commit()
        response.status_code = 200
        return address_json(same)
    if len(mine) >= MAX_ADDRESSES:
        raise HTTPException(status_code=409, detail=f"You can save up to {MAX_ADDRESSES} addresses")
    a = m.Address(user_id=user.id, is_default=not any(x.is_default for x in mine), created_at=now)
    _fill(a, body, now)
    db.add(a)
    db.commit()
    return address_json(a)


@router.put("/{address_id}")
def update_address(address_id: int, body: SavedAddress, request: Request, db: Db) -> dict:
    user = current_user(request, db)
    a = _one(db, user, address_id)
    _fill(a, body, request.app.state.clock.now())
    db.commit()
    return address_json(a)


@router.post("/{address_id}/default")
def make_default(address_id: int, request: Request, db: Db) -> list[dict]:
    user = current_user(request, db)
    chosen = _one(db, user, address_id)
    for a in _mine(db, user):
        a.is_default = a.id == chosen.id
    db.commit()
    return [address_json(a) for a in _mine(db, user)]


@router.delete("/{address_id}", status_code=204)
def delete_address(address_id: int, request: Request, db: Db) -> Response:
    user = current_user(request, db)
    a = _one(db, user, address_id)
    was_default = a.is_default
    db.delete(a)
    db.flush()
    rest = _mine(db, user)
    if was_default and rest:
        rest[0].is_default = True
    db.commit()
    return Response(status_code=204)
