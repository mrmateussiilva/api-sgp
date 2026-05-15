from auth.router import verify_password
from auth.models import User


async def test_change_password_uses_auth_prefix_once(client, admin_headers, test_session):
    response = await client.post(
        "/auth/change-password",
        json={
            "current_password": "StrongP@ss1",
            "new_password": "NewP@ss123",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Senha alterada com sucesso"}

    user = await test_session.get(User, 1)
    assert user is not None
    assert verify_password("NewP@ss123", user.password_hash)
    assert user.password_plain == "NewP@ss123"


async def test_change_password_rejects_wrong_current_password(client, admin_headers):
    response = await client.post(
        "/auth/change-password",
        json={
            "current_password": "senha-errada",
            "new_password": "NewP@ss123",
        },
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Senha atual incorreta"
