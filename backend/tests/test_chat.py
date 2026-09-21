def test_chat_rule_based_stats_intent(client, db_session):
    from app.models.city import City

    city = City(name="Chattown", slug="chattown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.commit()

    resp = client.post("/api/v1/chat", json={"city_id": city.id, "message": "how many problems are there", "history": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "rule_based"  # no LLM_API_KEY configured in tests
    assert "Chattown" in data["reply"]


def test_chat_rule_based_organizations_intent(client, db_session):
    from app.models.city import City

    city = City(name="Orgtown", slug="orgtown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.commit()

    resp = client.post("/api/v1/chat", json={"city_id": city.id, "message": "who can help with garbage", "history": []})
    assert resp.status_code == 200
    reply = resp.json()["reply"]
    assert "wastewarriors.org" in reply or "sulabhinternational.org" in reply


def test_chat_rejects_empty_message(client, db_session):
    from app.models.city import City

    city = City(name="Emptytown", slug="emptytown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.commit()

    resp = client.post("/api/v1/chat", json={"city_id": city.id, "message": "   ", "history": []})
    assert resp.status_code == 422


def test_chat_404_for_unknown_city(client):
    resp = client.post("/api/v1/chat", json={"city_id": 999999, "message": "hi", "history": []})
    assert resp.status_code == 404


def test_chat_conversation_history_accepted(client, db_session):
    from app.models.city import City

    city = City(name="Historytown", slug="historytown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.commit()

    resp = client.post(
        "/api/v1/chat",
        json={
            "city_id": city.id,
            "message": "what about risk scores",
            "history": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hi there!"}],
        },
    )
    assert resp.status_code == 200
