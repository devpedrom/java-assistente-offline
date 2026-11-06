from dataclasses import replace
import unittest

from java_assistant.memory.models import ProjectManifest, RequirementSnapshot, SessionState, VerificationSnapshot
from java_assistant.uml.models import JavaClass, JavaContract, JavaMember, Relationship, contract_from_dict, contract_to_dict


class MemoryModelTests(unittest.TestCase):
    def test_contract_round_trip_preserves_types_and_evidence(self):
        contract = JavaContract((JavaClass("Conta", (JavaMember("saldo", "Double", "private"),),
            (JavaMember("Conta", "Conta", "public", (("saldo", "Double"),)),)),),
            (Relationship("Base", "Conta", "inheritance", .98),), ("inferido",))
        self.assertEqual(contract, contract_from_dict(contract_to_dict(contract)))
        data = contract_to_dict(contract)
        data["classes"][0]["name"] = "../Conta"
        with self.assertRaises(ValueError):
            contract_from_dict(data)

    def test_document_round_trips_and_rejects_wrong_schema_or_types(self):
        docs = (ProjectManifest("abc"), RequirementSnapshot(JavaContract((), ()), "texto", "texto", "texto-" + "a"*64),
                SessionState(), VerificationSnapshot())
        for doc in docs:
            with self.subTest(doc=type(doc).__name__):
                self.assertEqual(doc, type(doc).from_dict(doc.to_dict()))
                data = doc.to_dict()
                data["schema_version"] = 99
                with self.assertRaises(ValueError):
                    type(doc).from_dict(data)
        with self.assertRaises(ValueError):
            ProjectManifest.from_dict({"schema_version": 1, "project_id": ""})
        with self.assertRaises(ValueError):
            SessionState.from_dict({"schema_version": 1, "source_hashes": {"../Conta.java": "a"*64}})

    def test_hash_maps_are_defensively_copied(self):
        hashes = {"Conta.java": "a"*64}
        state = SessionState(source_hashes=hashes)
        hashes.clear()
        self.assertIn("Conta.java", state.to_dict()["source_hashes"])
