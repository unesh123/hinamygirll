import sys
import re

file_path = "apps/api/hinaa_api/main.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Modify execute_tool to populate userId and conversationId
old_execute = '''    @app.post("/v1/tools/execute")
    async def execute_tool(request: ToolRequest) -> dict[str, Any]:
        tool_def = registry.get_tool(request.toolName)
        if not tool_def:
            raise HTTPException(status_code=404, detail="Tool not found")
            
        handler = registry._handlers.get(request.toolName)
        if not handler:
            raise HTTPException(status_code=500, detail="Tool handler not registered")
            
        try:
            import inspect
            from pydantic import BaseModel
            
            sig = inspect.signature(handler)
            parsed_params = request.parameters
            
            if sig.parameters:
                first_param = list(sig.parameters.values())[0]
                param_type = first_param.annotation
                if inspect.isclass(param_type) and issubclass(param_type, BaseModel):
                    parsed_params = param_type(**request.parameters)'''

new_execute = '''    @app.post("/v1/tools/execute")
    async def execute_tool(request: Request, body: ToolRequest) -> dict[str, Any]:
        tool_def = registry.get_tool(body.toolName)
        if not tool_def:
            raise HTTPException(status_code=404, detail="Tool not found")
            
        handler = registry._handlers.get(body.toolName)
        if not handler:
            raise HTTPException(status_code=500, detail="Tool handler not registered")
            
        try:
            import inspect
            from pydantic import BaseModel
            
            sig = inspect.signature(handler)
            parsed_params = body.parameters.copy()
            
            # Inject identity context if missing
            user_id = _resolve_user_id(request)
            if user_id:
                parsed_params.setdefault("userId", user_id)
            if "conversationId" not in parsed_params:
                conv_id = request.headers.get("X-Conversation-ID")
                if conv_id:
                    parsed_params["conversationId"] = conv_id
                    
            if sig.parameters:
                first_param = list(sig.parameters.values())[0]
                param_type = first_param.annotation
                if inspect.isclass(param_type) and issubclass(param_type, BaseModel):
                    parsed_params = param_type(**parsed_params)'''

content = content.replace(old_execute, new_execute)

# Also need to replace equest.toolName with ody.toolName in the remaining parts of execute_tool
old_request_toolname = '''                "id": str(uuid.uuid4()),
                "toolId": request.toolName,
                "status": "success",'''
new_request_toolname = '''                "id": str(uuid.uuid4()),
                "toolId": body.toolName,
                "status": "success",'''
content = content.replace(old_request_toolname, new_request_toolname)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
