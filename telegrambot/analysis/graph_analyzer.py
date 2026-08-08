import ast
import networkx as nx


class _CallGraphVisitor(ast.NodeVisitor):
    """
    NodeVisitor yang melacak konteks kelas & fungsi secara benar
    (push saat masuk scope, pop saat keluar scope), sehingga panggilan
    fungsi selalu diatribusikan ke fungsi terdekat yang membungkusnya
    (bukan ke fungsi luar jika ada fungsi bersarang / nested).
    """

    def __init__(self, graph: nx.DiGraph, file_path: str):
        self.graph = graph
        self.file_path = file_path
        self.class_stack: list[str] = []
        self.func_stack: list[str] = []

    def _qualified_name(self, func_name: str) -> str:
        class_name = self.class_stack[-1] if self.class_stack else None
        return f"{class_name}.{func_name}" if class_name else func_name

    def visit_ClassDef(self, node: ast.ClassDef):
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()  # <-- perbaikan: pop setelah selesai memproses isi kelas

    def visit_FunctionDef(self, node):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._handle_function(node)

    def _handle_function(self, node):
        full_name = self._qualified_name(node.name)
        self.graph.add_node(full_name, file=self.file_path, type="function")

        self.func_stack.append(full_name)
        self.generic_visit(node)  # masuk ke body; fungsi nested akan push namanya sendiri
        self.func_stack.pop()

    def visit_Call(self, node: ast.Call):
        if self.func_stack:
            caller = self.func_stack[-1]  # fungsi terdekat yang membungkus, bukan fungsi paling luar
            called_name = self._resolve_call_name(node.func)
            if called_name:
                self.graph.add_edge(caller, called_name)
        self.generic_visit(node)

    def _resolve_call_name(self, func_node) -> str | None:
        if isinstance(func_node, ast.Name):
            return func_node.id
        if isinstance(func_node, ast.Attribute):
            # self.foo() / cls.foo() -> coba resolve ke "NamaKelas.foo" agar tidak
            # tertukar dengan method "foo" di kelas lain
            if (
                isinstance(func_node.value, ast.Name)
                and func_node.value.id in ("self", "cls")
                and self.class_stack
            ):
                return f"{self.class_stack[-1]}.{func_node.attr}"
            # obj.method() lain -> tetap fallback ke nama method saja
            return func_node.attr
        return None


class GraphAnalyzer:
    def __init__(self):
        self.graph = nx.DiGraph()

    def analyze_code_structure(self, code_content: str, file_path: str) -> None:
        """
        Membedah kode menggunakan AST dan membangun graf pemanggilan fungsi.
        Menggunakan ast.NodeVisitor (bukan ast.walk berlapis) supaya konteks
        kelas/fungsi terlacak dengan benar melalui scope masuk-keluar.
        """
        try:
            tree = ast.parse(code_content)
        except SyntaxError as e:
            print(f"--- ERROR DI FILE: {file_path} ---")
            print(f"Isi Kode: {code_content[:50]}...")
            print(f"Detail Error: {e}")
            return

        try:
            visitor = _CallGraphVisitor(self.graph, file_path)
            visitor.visit(tree)
        except Exception as e:
            print(f"Error menganalisis {file_path}: {e}")

    def get_impact_analysis(self, target_function: str) -> dict:
        """
        Mencari fungsi yang memanggil target_function (predecessors)
        dan fungsi yang dipanggil oleh target_function, langsung maupun
        tidak langsung (descendants).
        """
        if target_function not in self.graph:
            return {"affected_by": [], "affects": []}

        return {
            "affected_by": list(self.graph.predecessors(target_function)),
            "affects": list(nx.descendants(self.graph, target_function)),
        }

    def get_call_chain(self, start_node: str, end_node: str) -> list[str] | None:
        """
        Mencari jalur pemanggilan fungsi terpendek dari start_node ke end_node.
        Mengembalikan None jika salah satu node tidak ada atau tidak ada jalur.
        """
        try:
            return nx.shortest_path(self.graph, source=start_node, target=end_node)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def export_graph(self) -> dict:
        """Ekspor graf ke format dictionary untuk JSON/visualisasi."""
        return nx.node_link_data(self.graph)
