"""Pruebas unitarias de hashing y firma de sesiones, sin crear cuentas."""

import sys
import unittest
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOCAL))
import entorno  # noqa: E402

entorno.cargar()
sys.path.insert(0, str(LOCAL.parent / "app"))

from fastapi import HTTPException  # noqa: E402
import auth  # noqa: E402


class AutenticacionUnitarias(unittest.TestCase):
    def test_password_se_guarda_derivada_y_se_verifica(self):
        hash_guardado = auth.hash_password("un-password-seguro-para-test")
        self.assertNotIn("un-password-seguro-para-test", hash_guardado)
        self.assertTrue(auth.verificar_password("un-password-seguro-para-test", hash_guardado))
        self.assertFalse(auth.verificar_password("otro-password", hash_guardado))

    def test_password_corta_se_rechaza(self):
        with self.assertRaises(ValueError):
            auth.hash_password("corta")

    def test_token_firmado_y_token_alterado(self):
        token = auth._token_para(
            {"id": "00000000-0000-0000-0000-000000000001", "email": "test@example.test"}
        )
        self.assertEqual(auth._decodificar_token(token)["email"], "test@example.test")
        partes = token.split(".")
        partes[1] = ("A" if partes[1][0] != "A" else "B") + partes[1][1:]
        with self.assertRaises(HTTPException):
            auth._decodificar_token(".".join(partes))


if __name__ == "__main__":
    unittest.main()
