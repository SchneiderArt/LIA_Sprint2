import io
import pytest
from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_upload_sem_bpmn():
    pdf_bytes = io.BytesIO(b"%PDF-1.4 teste")
    resp = client.post(
        "/analisar-processo",
        files={"pdf_file": ("doc.pdf", pdf_bytes, "application/pdf")},
        data={"pipeline": "both"},
    )
    assert resp.status_code == 422  # campo bpmn_file obrigatório


def test_upload_extensao_errada():
    bpmn_bytes = io.BytesIO(b"<definitions/>")
    pdf_bytes = io.BytesIO(b"%PDF-1.4")
    resp = client.post(
        "/analisar-processo",
        files={
            "bpmn_file": ("processo.xml", bpmn_bytes, "application/xml"),  # extensão errada
            "pdf_file": ("doc.pdf", pdf_bytes, "application/pdf"),
        },
        data={"pipeline": "both"},
    )
    assert resp.status_code == 400
