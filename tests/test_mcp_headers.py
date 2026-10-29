"""Tests des en-têtes d'authentification envoyés au serveur MCP Developer Knowledge."""

from __future__ import annotations

import google.auth
import google.oauth2.credentials
import pytest

from paa_coach import agent, config


class _CredsServiceAccount:
    """Identifiants de compte de service factices (Cloud Run)."""

    valid = True
    token = "jeton-sa"
    quota_project_id = None


def _creds_utilisateur(quota_project_id: str | None) -> google.oauth2.credentials.Credentials:
    creds = google.oauth2.credentials.Credentials(token="jeton-user", quota_project_id=quota_project_id)
    return creds


@pytest.fixture(autouse=True)
def _sans_cle_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "DEVELOPER_KNOWLEDGE_API_KEY", None)
    monkeypatch.setattr(config, "GOOGLE_CLOUD_PROJECT", "projet-test")
    monkeypatch.setattr(google.oauth2.credentials.Credentials, "valid", property(lambda self: True))


def test_identifiants_utilisateur_ajoutent_le_projet_de_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google.auth, "default", lambda scopes=None: (_creds_utilisateur(None), None))
    headers = agent._mcp_header_provider(None)
    assert headers["Authorization"] == "Bearer jeton-user"
    assert headers["x-goog-user-project"] == "projet-test"


def test_projet_de_quota_des_adc_prioritaire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google.auth, "default", lambda scopes=None: (_creds_utilisateur("quota-adc"), None))
    assert agent._mcp_header_provider(None)["x-goog-user-project"] == "quota-adc"


def test_compte_de_service_sans_projet_de_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google.auth, "default", lambda scopes=None: (_CredsServiceAccount(), None))
    headers = agent._mcp_header_provider(None)
    assert headers["Authorization"] == "Bearer jeton-sa"
    assert "x-goog-user-project" not in headers
