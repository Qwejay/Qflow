import ast
import copy
import json
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "main.py"


def extract_class_with_method(class_name, method_name, namespace=None):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    source_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node for node in source_class.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    probe = ast.ClassDef(
        name="Probe",
        bases=[],
        keywords=[],
        body=[copy.deepcopy(method)],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[]))
    scope = {"json": json}
    if namespace:
        scope.update(namespace)
    exec(compile(module, str(SOURCE), "exec"), scope)
    return scope["Probe"]


class FakePropertyPanel:
    def clear(self):
        pass


class FakeApp:
    property_panel = FakePropertyPanel()


class FakeEditor:
    def __init__(self, current, load_result):
        self.current = current
        self.load_result = load_result
        self.app = FakeApp()
        self.load_attempts = []

    def get_data(self):
        return copy.deepcopy(self.current)

    def load_data(self, data):
        self.load_attempts.append(copy.deepcopy(data))
        if self.load_result:
            self.current = copy.deepcopy(data)
        return self.load_result


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.CoreProbe = extract_class_with_method(
            "AutomationCore", "_get_next_links"
        )
        cls.HistoryManager = extract_class_with_method(
            "HistoryManager", "undo"
        )
        # Include redo in the same probe so its history semantics are tested too.
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        source_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "HistoryManager"
        )
        redo = next(
            node for node in source_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "redo"
        )
        probe = ast.ClassDef(
            name="HistoryProbe",
            bases=[],
            keywords=[],
            body=[
                copy.deepcopy(next(
                    node for node in source_class.body
                    if isinstance(node, ast.FunctionDef) and node.name == "undo"
                )),
                copy.deepcopy(redo),
            ],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[]))
        scope = {}
        exec(compile(module, str(SOURCE), "exec"), scope)
        cls.HistoryManager = scope["HistoryProbe"]

    def test_legacy_link_without_source_port_uses_out(self):
        core = self.CoreProbe()
        core.project = {
            "nodes": {"a": {}, "b": {}, "c": {}},
            "links": [
                {"source": "a", "target": "b"},
                {"source": "a", "source_port": "yes", "target": "c"},
                {"source": "a", "target": "missing"},
            ],
        }
        self.assertEqual(core._get_next_links("a", "out"), ["b"])
        self.assertEqual(core._get_next_links("a", "yes"), ["c"])

    def test_undo_failure_does_not_mutate_history_stacks(self):
        editor = FakeEditor({"version": 2}, load_result=False)
        manager = self.HistoryManager(editor)
        manager.undo_stack = [{"version": 1}]
        manager.redo_stack = [{"version": 0}]

        manager.undo()

        self.assertEqual(manager.undo_stack, [{"version": 1}])
        self.assertEqual(manager.redo_stack, [{"version": 0}])
        self.assertEqual(editor.current, {"version": 2})

    def test_redo_failure_does_not_mutate_history_stacks(self):
        editor = FakeEditor({"version": 2}, load_result=False)
        manager = self.HistoryManager(editor)
        manager.undo_stack = [{"version": 1}]
        manager.redo_stack = [{"version": 0}]

        manager.redo()

        self.assertEqual(manager.undo_stack, [{"version": 1}])
        self.assertEqual(manager.redo_stack, [{"version": 0}])
        self.assertEqual(editor.current, {"version": 2})

    def test_undo_success_moves_current_state_to_redo(self):
        editor = FakeEditor({"version": 2}, load_result=True)
        manager = self.HistoryManager(editor)
        manager.undo_stack = [{"version": 1}]

        manager.undo()

        self.assertEqual(editor.current, {"version": 1})
        self.assertEqual(manager.undo_stack, [])
        self.assertEqual(manager.redo_stack, [{"version": 2}])

    def test_redo_success_moves_current_state_to_undo(self):
        editor = FakeEditor({"version": 1}, load_result=True)
        manager = self.HistoryManager(editor)
        manager.redo_stack = [{"version": 2}]

        manager.redo()

        self.assertEqual(editor.current, {"version": 2})
        self.assertEqual(manager.redo_stack, [])
        self.assertEqual(manager.undo_stack, [{"version": 1}])

    def test_legacy_link_deletion_uses_default_output_port(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("l.get('source_port', 'out')==next(", source)


if __name__ == "__main__":
    unittest.main()
