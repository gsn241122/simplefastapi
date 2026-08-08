import uuid
from typing import Any, Dict

class ApprovalManager:
    def __init__(self):
        self.pending_tasks: Dict[str, Dict[str, Any]] = {}

    def add_task(self, name: str, arguments: Dict[str, Any]) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.pending_tasks[task_id] = {"name": name, "arguments": arguments}
        return task_id

    def get_task(self, task_id: str):
        return self.pending_tasks.pop(task_id, None)

    async def execute_task(self, task_id: str, dispatcher: Any):
        task = self.get_task(task_id)
        if not task:
            return {"content": [{"type": "text", "text": "Task tidak ditemukan atau sudah kadaluwarsa."}], "isError": True}
        
        # Eksekusi langsung melalui dispatcher
        return await dispatcher.call_real(task["name"], task["arguments"])

approval_manager = ApprovalManager()
