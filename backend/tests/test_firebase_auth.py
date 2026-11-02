import asyncio

import pytest

from app.services.firebase_auth import (
    FirebaseAccountLinkError,
    sync_firebase_user,
    verify_firebase_id_token,
)


class FakeUserCollection:
    def __init__(self, users=None):
        self.users = list(users or [])
        self.next_id = 1

    async def find_one(self, query):
        for user in self.users:
            if all(user.get(key) == value for key, value in query.items()):
                return dict(user)
        return None

    async def insert_one(self, document):
        if any(
            row.get("firebase_uid") == document.get("firebase_uid")
            or row.get("email_normalized") == document.get("email_normalized")
            for row in self.users
        ):
            raise RuntimeError("duplicate identity")
        row = dict(document)
        row["_id"] = self.next_id
        self.next_id += 1
        self.users.append(row)
        return type("InsertResult", (), {"inserted_id": row["_id"]})()

    async def update_one(self, query, update):
        for user in self.users:
            if all(user.get(key) == value for key, value in query.items()):
                user.update(update.get("$set", {}))
                return type("UpdateResult", (), {"modified_count": 1})()
        return type("UpdateResult", (), {"modified_count": 0})()


class FakeDatabase:
    def __init__(self, users=None):
        self.user = FakeUserCollection(users)


def run(coro):
    return asyncio.run(coro)


def test_firebase_identity_creates_a_default_mongo_profile():
    db = FakeDatabase()
    user = run(
        sync_firebase_user(
            db,
            {
                "uid": "firebase-user-123",
                "email": "New.User@example.com",
                "email_verified": True,
                "name": "New User",
            },
        )
    )

    assert user["firebase_uid"] == "firebase-user-123"
    assert user["user_id"] == "firebase-user-123"
    assert user["email_normalized"] == "new.user@example.com"
    assert user["role"] == "user"
    assert user["email_verified"] is True


def test_firebase_identity_links_existing_profile_without_downgrading_role():
    db = FakeDatabase(
        [
            {
                "_id": "existing-user",
                "user_id": "existing-user",
                "email": "owner@example.com",
                "email_normalized": "owner@example.com",
                "role": "admin",
                "ai_language": "ta",
                "two_factor_enabled": True,
            }
        ]
    )

    user = run(
        sync_firebase_user(
            db,
            {
                "sub": "firebase-owner-uid",
                "email": "OWNER@example.com",
                "email_verified": True,
            },
        )
    )

    assert user["user_id"] == "existing-user"
    assert user["firebase_uid"] == "firebase-owner-uid"
    assert user["role"] == "admin"
    assert user["ai_language"] == "ta"
    assert user["two_factor_enabled"] is True


def test_firebase_identity_cannot_take_over_a_profile_linked_to_another_uid():
    db = FakeDatabase(
        [
            {
                "_id": "linked-user",
                "user_id": "linked-user",
                "firebase_uid": "original-firebase-uid",
                "email": "owner@example.com",
                "email_normalized": "owner@example.com",
                "role": "admin",
            }
        ]
    )

    with pytest.raises(FirebaseAccountLinkError):
        run(
            sync_firebase_user(
                db,
                {
                    "uid": "different-firebase-uid",
                    "email": "owner@example.com",
                    "email_verified": True,
                },
            )
        )


def test_firebase_identity_rejects_unverified_email():
    with pytest.raises(ValueError, match="verified email"):
        run(
            sync_firebase_user(
                FakeDatabase(),
                {
                    "uid": "firebase-user-123",
                    "email": "user@example.com",
                    "email_verified": False,
                },
            )
        )


def test_empty_firebase_id_token_is_rejected_before_admin_initialization():
    with pytest.raises(ValueError, match="Invalid Firebase ID token"):
        verify_firebase_id_token("")
