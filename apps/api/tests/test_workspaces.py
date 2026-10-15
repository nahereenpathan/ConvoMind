"""Comprehensive integration and unit tests for Workspace Management module."""

import uuid
from typing import Dict, Tuple
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import WorkspaceRole


async def create_user_and_token(
    client: AsyncClient, name: str = "Test User"
) -> Tuple[Dict, str]:
    """Register and log in a user, returning user dict and access token."""
    email = f"ws_test_{uuid.uuid4().hex[:8]}@convomind.ai"
    password = "Password123!"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_data = reg_res.json()

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    return user_data, token


def auth_header(token: str) -> Dict[str, str]:
    """Helper to build bearer authorization header."""
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_workspace():
    """1. Authenticated user can create a workspace."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token = await create_user_and_token(client, "Owner User")

        payload = {
            "name": "Acme Software",
            "description": "Software development team",
        }
        res = await client.post(
            "/api/v1/workspaces",
            json=payload,
            headers=auth_header(token),
        )
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Acme Software"
        assert data["description"] == "Software development team"
        assert "slug" in data
        assert data["slug"].startswith("acme-software")
        assert "id" in data


@pytest.mark.asyncio
async def test_creator_automatically_becomes_owner():
    """2. Workspace creator automatically becomes OWNER."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        user, token = await create_user_and_token(client, "Creator User")

        res = await client.post(
            "/api/v1/workspaces",
            json={"name": "Owner Check Org"},
            headers=auth_header(token),
        )
        assert res.status_code == 201
        ws_id = res.json()["id"]

        # Check members list
        members_res = await client.get(
            f"/api/v1/workspaces/{ws_id}/members",
            headers=auth_header(token),
        )
        assert members_res.status_code == 200
        members = members_res.json()
        assert len(members) == 1
        assert members[0]["user_id"] == user["id"]
        assert members[0]["role"] == WorkspaceRole.OWNER.value


@pytest.mark.asyncio
async def test_list_my_workspaces():
    """3. User can list their workspaces."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token1 = await create_user_and_token(client, "User 1")
        _, token2 = await create_user_and_token(client, "User 2")

        # User 1 creates 2 workspaces
        ws1_res = await client.post(
            "/api/v1/workspaces",
            json={"name": "Workspace Alpha"},
            headers=auth_header(token1),
        )
        ws2_res = await client.post(
            "/api/v1/workspaces",
            json={"name": "Workspace Beta"},
            headers=auth_header(token1),
        )

        # User 2 creates 1 workspace
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Workspace Gamma"},
            headers=auth_header(token2),
        )

        # User 1 lists workspaces
        list1_res = await client.get(
            "/api/v1/workspaces",
            headers=auth_header(token1),
        )
        assert list1_res.status_code == 200
        list1 = list1_res.json()
        ids1 = [ws["id"] for ws in list1]
        assert ws1_res.json()["id"] in ids1
        assert ws2_res.json()["id"] in ids1
        assert len(list1) == 2

        # Verify role is included
        for item in list1:
            assert item["role"] == WorkspaceRole.OWNER.value


@pytest.mark.asyncio
async def test_get_workspace_details():
    """4. User can retrieve a workspace they belong to."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token = await create_user_and_token(client)
        create_res = await client.post(
            "/api/v1/workspaces",
            json={"name": "Detail Workspace", "description": "Details here"},
            headers=auth_header(token),
        )
        ws_id = create_res.json()["id"]

        get_res = await client.get(
            f"/api/v1/workspaces/{ws_id}",
            headers=auth_header(token),
        )
        assert get_res.status_code == 200
        assert get_res.json()["id"] == ws_id
        assert get_res.json()["name"] == "Detail Workspace"
        assert get_res.json()["description"] == "Details here"


@pytest.mark.asyncio
async def test_non_member_cannot_retrieve_workspace():
    """5. Non-member cannot retrieve another workspace (returns 404)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        _, token_stranger = await create_user_and_token(client, "Stranger")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Private Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        res = await client.get(
            f"/api/v1/workspaces/{ws['id']}",
            headers=auth_header(token_stranger),
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "Workspace not found."


@pytest.mark.asyncio
async def test_owner_can_update_workspace():
    """6. Owner can update workspace."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token = await create_user_and_token(client)
        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Old Name"},
                headers=auth_header(token),
            )
        ).json()

        update_res = await client.patch(
            f"/api/v1/workspaces/{ws['id']}",
            json={"name": "New Name", "description": "New description"},
            headers=auth_header(token),
        )
        assert update_res.status_code == 200
        data = update_res.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New description"


@pytest.mark.asyncio
async def test_member_cannot_update_workspace():
    """7. Member cannot update restricted workspace information (returns 403)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_member, token_member = await create_user_and_token(client, "Member")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Protected Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        # Add member as regular MEMBER
        add_res = await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_member["email"], "role": "MEMBER"},
            headers=auth_header(token_owner),
        )
        assert add_res.status_code == 201

        # Regular member tries to update workspace
        update_res = await client.patch(
            f"/api/v1/workspaces/{ws['id']}",
            json={"name": "Hacked Org"},
            headers=auth_header(token_member),
        )
        assert update_res.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_delete_workspace():
    """8. Owner can delete workspace."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token = await create_user_and_token(client)
        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "To Delete"},
                headers=auth_header(token),
            )
        ).json()

        del_res = await client.delete(
            f"/api/v1/workspaces/{ws['id']}",
            headers=auth_header(token),
        )
        assert del_res.status_code == 200
        assert "deleted" in del_res.json()["message"].lower()

        # Verify it no longer exists
        get_res = await client.get(
            f"/api/v1/workspaces/{ws['id']}",
            headers=auth_header(token),
        )
        assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_admin_cannot_delete_workspace():
    """9. Admin cannot delete workspace (returns 403)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_admin, token_admin = await create_user_and_token(client, "Admin")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Safe From Admin Deletion"},
                headers=auth_header(token_owner),
            )
        ).json()

        # Owner adds user as ADMIN
        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_admin["email"], "role": "ADMIN"},
            headers=auth_header(token_owner),
        )

        # Admin tries to delete workspace
        del_res = await client.delete(
            f"/api/v1/workspaces/{ws['id']}",
            headers=auth_header(token_admin),
        )
        assert del_res.status_code == 403


@pytest.mark.asyncio
async def test_member_can_view_members():
    """10. Member can view members."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_member, token_member = await create_user_and_token(client, "Member")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Team View"},
                headers=auth_header(token_owner),
            )
        ).json()

        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_member["email"], "role": "MEMBER"},
            headers=auth_header(token_owner),
        )

        # Regular member views members
        list_res = await client.get(
            f"/api/v1/workspaces/{ws['id']}/members",
            headers=auth_header(token_member),
        )
        assert list_res.status_code == 200
        members = list_res.json()
        assert len(members) == 2


@pytest.mark.asyncio
async def test_owner_can_add_member():
    """11. Owner can add a member."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_target, _ = await create_user_and_token(client, "Target")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Add Member Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        add_res = await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_target["email"], "role": "member"},
            headers=auth_header(token_owner),
        )
        assert add_res.status_code == 201
        data = add_res.json()
        assert data["user_id"] == user_target["id"]
        assert data["role"] == WorkspaceRole.MEMBER.value
        assert data["user"]["email"] == user_target["email"]


@pytest.mark.asyncio
async def test_admin_can_add_member_if_policy_allows():
    """12. Admin can add a member if policy allows (can add MEMBER)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_admin, token_admin = await create_user_and_token(client, "Admin")
        user_new, _ = await create_user_and_token(client, "New Hire")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Admin Invite Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        # Make user an ADMIN
        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_admin["email"], "role": "ADMIN"},
            headers=auth_header(token_owner),
        )

        # Admin invites new hire as MEMBER
        add_res = await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_new["email"], "role": "MEMBER"},
            headers=auth_header(token_admin),
        )
        assert add_res.status_code == 201
        assert add_res.json()["user_id"] == user_new["id"]


@pytest.mark.asyncio
async def test_duplicate_membership_rejected():
    """13. Duplicate membership is rejected safely (returns 409)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_target, _ = await create_user_and_token(client, "Target")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Dup Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        # Add once
        res1 = await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_target["email"], "role": "MEMBER"},
            headers=auth_header(token_owner),
        )
        assert res1.status_code == 201

        # Add duplicate
        res2 = await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_target["email"], "role": "MEMBER"},
            headers=auth_header(token_owner),
        )
        assert res2.status_code == 409
        assert "already a member" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_existent_user_cannot_be_added():
    """14. Non-existent user cannot be added (returns 404)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Ghost Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        ghost_email = f"ghost_{uuid.uuid4().hex[:8]}@convomind.ai"
        res = await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": ghost_email, "role": "MEMBER"},
            headers=auth_header(token_owner),
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_owner_can_update_member_role():
    """15. Owner can update member role."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_target, _ = await create_user_and_token(client, "Target")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Role Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_target["email"], "role": "MEMBER"},
            headers=auth_header(token_owner),
        )

        # Promote to ADMIN
        patch_res = await client.patch(
            f"/api/v1/workspaces/{ws['id']}/members/{user_target['id']}",
            json={"role": "ADMIN"},
            headers=auth_header(token_owner),
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["role"] == WorkspaceRole.ADMIN.value


@pytest.mark.asyncio
async def test_admin_cannot_modify_or_demote_owner():
    """16. Admin cannot modify/demote owner (returns 403)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        user_owner, token_owner = await create_user_and_token(client, "Owner")
        user_admin, token_admin = await create_user_and_token(client, "Admin")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Owner Protection Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_admin["email"], "role": "ADMIN"},
            headers=auth_header(token_owner),
        )

        # Admin attempts to demote owner to MEMBER
        demote_res = await client.patch(
            f"/api/v1/workspaces/{ws['id']}/members/{user_owner['id']}",
            json={"role": "MEMBER"},
            headers=auth_header(token_admin),
        )
        assert demote_res.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_modify_another_member():
    """17. Member cannot modify another member (returns 403)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_m1, token_m1 = await create_user_and_token(client, "Member 1")
        user_m2, _ = await create_user_and_token(client, "Member 2")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Member Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_m1["email"], "role": "MEMBER"},
            headers=auth_header(token_owner),
        )
        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_m2["email"], "role": "MEMBER"},
            headers=auth_header(token_owner),
        )

        # Member 1 attempts to change Member 2 role
        res = await client.patch(
            f"/api/v1/workspaces/{ws['id']}/members/{user_m2['id']}",
            json={"role": "ADMIN"},
            headers=auth_header(token_m1),
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_remove_member():
    """18. Owner can remove a member."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_target, _ = await create_user_and_token(client, "Target")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Removal Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_target["email"], "role": "MEMBER"},
            headers=auth_header(token_owner),
        )

        # Owner removes member
        del_res = await client.delete(
            f"/api/v1/workspaces/{ws['id']}/members/{user_target['id']}",
            headers=auth_header(token_owner),
        )
        assert del_res.status_code == 200

        # Verify member is gone
        list_res = await client.get(
            f"/api/v1/workspaces/{ws['id']}/members",
            headers=auth_header(token_owner),
        )
        member_ids = [m["user_id"] for m in list_res.json()]
        assert user_target["id"] not in member_ids


@pytest.mark.asyncio
async def test_owner_cannot_remove_self_when_sole_owner():
    """19. Owner cannot accidentally remove themselves / delete ownership."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        user_owner, token_owner = await create_user_and_token(client, "Sole Owner")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Sole Owner Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        # Sole owner tries to remove self
        del_res = await client.delete(
            f"/api/v1/workspaces/{ws['id']}/members/{user_owner['id']}",
            headers=auth_header(token_owner),
        )
        assert del_res.status_code == 400
        assert "sole workspace owner" in del_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected():
    """20. Unauthenticated requests are rejected with 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        random_id = uuid.uuid4()

        # GET workspaces
        res = await client.get("/api/v1/workspaces")
        assert res.status_code == 401

        # POST workspace
        res = await client.post("/api/v1/workspaces", json={"name": "No Auth"})
        assert res.status_code == 401

        # GET workspace details
        res = await client.get(f"/api/v1/workspaces/{random_id}")
        assert res.status_code == 401

        # DELETE workspace
        res = await client.delete(f"/api/v1/workspaces/{random_id}")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_workspace_idor_attempts_rejected():
    """21. Workspace IDOR attempts are rejected."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_victim = await create_user_and_token(client, "Victim")
        _, token_attacker = await create_user_and_token(client, "Attacker")

        ws_victim = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Confidential Workspace"},
                headers=auth_header(token_victim),
            )
        ).json()

        # Attacker tries to GET victim's workspace
        res_get = await client.get(
            f"/api/v1/workspaces/{ws_victim['id']}",
            headers=auth_header(token_attacker),
        )
        assert res_get.status_code == 404

        # Attacker tries to PATCH victim's workspace
        res_patch = await client.patch(
            f"/api/v1/workspaces/{ws_victim['id']}",
            json={"name": "Attacked"},
            headers=auth_header(token_attacker),
        )
        assert res_patch.status_code == 404

        # Attacker tries to DELETE victim's workspace
        res_del = await client.delete(
            f"/api/v1/workspaces/{ws_victim['id']}",
            headers=auth_header(token_attacker),
        )
        assert res_del.status_code == 404

        # Attacker tries to GET members
        res_members = await client.get(
            f"/api/v1/workspaces/{ws_victim['id']}/members",
            headers=auth_header(token_attacker),
        )
        assert res_members.status_code == 404


@pytest.mark.asyncio
async def test_invalid_uuid_handled_correctly():
    """22. Invalid UUID is handled correctly with 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token = await create_user_and_token(client)

        res = await client.get(
            "/api/v1/workspaces/not-a-valid-uuid",
            headers=auth_header(token),
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_member_can_leave_workspace():
    """23. Regular member can remove themselves (leave workspace)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_member, token_member = await create_user_and_token(client, "Member")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Voluntary Departure Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_member["email"], "role": "MEMBER"},
            headers=auth_header(token_owner),
        )

        # Member leaves the workspace
        leave_res = await client.delete(
            f"/api/v1/workspaces/{ws['id']}/members/{user_member['id']}",
            headers=auth_header(token_member),
        )
        assert leave_res.status_code == 200

        # Now member cannot view workspace
        get_res = await client.get(
            f"/api/v1/workspaces/{ws['id']}",
            headers=auth_header(token_member),
        )
        assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_admin_cannot_remove_fellow_admin():
    """24. Admin cannot remove other admins (returns 403)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _, token_owner = await create_user_and_token(client, "Owner")
        user_admin1, token_admin1 = await create_user_and_token(client, "Admin 1")
        user_admin2, _ = await create_user_and_token(client, "Admin 2")

        ws = (
            await client.post(
                "/api/v1/workspaces",
                json={"name": "Multi Admin Org"},
                headers=auth_header(token_owner),
            )
        ).json()

        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_admin1["email"], "role": "ADMIN"},
            headers=auth_header(token_owner),
        )
        await client.post(
            f"/api/v1/workspaces/{ws['id']}/members",
            json={"email": user_admin2["email"], "role": "ADMIN"},
            headers=auth_header(token_owner),
        )

        # Admin 1 attempts to remove Admin 2
        del_res = await client.delete(
            f"/api/v1/workspaces/{ws['id']}/members/{user_admin2['id']}",
            headers=auth_header(token_admin1),
        )
        assert del_res.status_code == 403
