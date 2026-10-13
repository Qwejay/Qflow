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
        import threading
        import time
        cls.StartProbe = extract_class_with_method(
            "AutomationCore", "start",
            {"threading": threading, "time": time}
        )
        cls.LoadProjectProbe = extract_class_with_method(
            "AutomationCore", "load_project",
            {"safe_float": lambda value, default=0.0: float(value),
             "get_scale_factor": lambda: (1.0, 1.0),
             "ImageUtils": type("ImageUtilsStub", (), {"b64_to_img": staticmethod(lambda value: None)})}
        )
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        source_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "HistoryManager"
        )
        module = ast.fix_missing_locations(
            ast.Module(body=[copy.deepcopy(source_class)], type_ignores=[])
        )
        scope = {"json": json}
        exec(compile(module, str(SOURCE), "exec"), scope)
        cls.HistoryManager = scope["HistoryManager"]

    def test_concurrent_start_requests_only_launch_one_engine(self):
        import threading

        class Event:
            def __init__(self, set_value=False):
                self.value = set_value
            def clear(self):
                self.value = False
            def set(self):
                self.value = True

        class FakeThread:
            starts = 0
            def __init__(self, *args, **kwargs):
                pass
            def start(self):
                FakeThread.starts += 1

        class App:
            def iconify(self):
                pass
            def after(self, *args):
                pass
            def reset_ui_state(self):
                pass

        class Engine:
            log = lambda *args: None

        engine = Engine()
        engine.thread_lock = threading.Lock()
        engine.running = False
        engine.project = {"nodes": {"start": {"type": "start"}}}
        engine.paused = False
        engine.stop_event = Event()
        engine.pause_event = Event(True)
        engine.active_threads = 0
        engine.pending_nodes = []
        engine.runtime_memory = {}
        engine.context = {}
        engine.performance_stats = {}
        engine.app = App()

        from unittest.mock import patch
        with patch("threading.Thread", FakeThread):
            threads = [
                threading.Thread(target=engine.start)
                for _ in range(8)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertTrue(engine.running)
        self.assertEqual(FakeThread.starts, 1)

    def test_queued_worker_launch_failure_clears_queue_and_stops_engine(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        core = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "AutomationCore"
        )
        worker = next(
            node for node in core.body
            if isinstance(node, ast.FunctionDef) and node.name == "_process_node_thread"
        )
        calls = [
            node.func.attr
            for node in ast.walk(worker)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        self.assertIn("set", calls)
        self.assertIn("clear", calls)
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("已停止剩余任务", source)

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

    def test_invalid_metadata_does_not_replace_current_engine_project(self):
        core = self.LoadProjectProbe()
        core.project = {"nodes": {"existing": {}}}
        core.scaling_ratio = 2.0
        core.breakpoints = {"existing"}

        with self.assertRaises(ValueError):
            core.load_project({"nodes": {}, "metadata": []})

        self.assertEqual(core.project, {"nodes": {"existing": {}}})
        self.assertEqual(core.scaling_ratio, 2.0)
        self.assertEqual(core.breakpoints, {"existing"})

    def test_project_load_preflights_images_before_engine_or_canvas_mutation(self):
        source = SOURCE.read_text(encoding="utf-8")
        method_start = source.index("    def load_data(self, data, _rollback=False):")
        method = source[method_start:source.index("\nclass PropertyPanel", method_start)]
        self.assertLess(method.index("prepare_images(data.get('nodes', {}))"), method.index("self.app.core.load_project(data)"))
        self.assertLess(method.index("prepare_images(data.get('nodes', {}))"), method.index('self.delete("all")'))

    def test_long_running_detection_nodes_honor_pause(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        core = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "AutomationCore"
        )
        execute = next(
            node for node in core.body
            if isinstance(node, ast.FunctionDef) and node.name == "_execute_node"
        )
        for node_type in ("if_sound", "if_static"):
            branch = next(
                node for node in ast.walk(execute)
                if isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "ntype"
                and any(
                    isinstance(value, ast.Constant) and value.value == node_type
                    for value in node.test.comparators
                )
            )
            loops = [
                node for node in ast.walk(branch)
                if isinstance(node, ast.While)
            ]
            self.assertTrue(loops, f"{node_type} should contain a polling loop")
            self.assertTrue(
                any(
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "_check_pause"
                    for loop in loops
                    for call in ast.walk(loop)
                ),
                f"{node_type} polling loop must honor pause",
            )


if __name__ == "__main__":
    unittest.main()
