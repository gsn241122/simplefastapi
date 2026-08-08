from telegram import Update
from telegram.ext import ContextTypes
from mcp_agent.approval_manager import ApprovalManager

async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith(("approve_", "reject_")):
        return

    action, task_id = data.split("_")
    approval_manager = context.application.bot_data.get("approval_manager")
    unified_tools = context.application.bot_data.get("unified_tools")
    
    if action == "approve":
        result = await approval_manager.execute_task(task_id, unified_tools)
        await query.edit_message_text(f"✅ Tugas disetujui.\nHasil: {result}")
    else:
        approval_manager.remove_task(task_id)
        await query.edit_message_text("❌ Tugas ditolak.")
