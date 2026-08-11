import sys
import re

file_path = "apps/api/hinaa_api/tools/image_generate.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add userId and conversationId to ImageGenerateParams
old_params = '''class ImageGenerateParams(BaseModel):
    prompt: str
    negative_prompt: str = ""
    seed: Optional[int] = None
    count: int = 1
    mode: str = "fast" # "fast" (768x768), "quality" (1024x1024), "ultra" (1024x1536)
    strategy: str = "VARIATIONS"'''
new_params = '''class ImageGenerateParams(BaseModel):
    prompt: str
    negative_prompt: str = ""
    seed: Optional[int] = None
    count: int = 1
    mode: str = "fast" # "fast" (768x768), "quality" (1024x1024), "ultra" (1024x1536)
    strategy: str = "VARIATIONS"
    userId: Optional[str] = None
    conversationId: Optional[str] = None'''
content = content.replace(old_params, new_params)

# Remove the dummy insertion code
old_dummy = '''    session_factory = get_session_factory(settings)
    with session_factory() as session:
        from sqlalchemy import text
        session.execute(text("INSERT OR IGNORE INTO users (id, auth_subject, status, memory_enabled) VALUES ('default', 'default', 'active', 1)"))
        session.execute(text("INSERT OR IGNORE INTO conversations (id, user_id, companion_id, title) VALUES ('default', 'default', 'hiro', 'default')"))
        session.commit()
        gen_set = GenerationSet(
            id=generation_set_id,
            user_id="default",
            conversation_id="default",
            prompt=params.prompt,
            workflow_mode=params.mode
        )
        session.add(gen_set)
        session.commit()'''
        
new_dummy = '''    session_factory = get_session_factory(settings)
    with session_factory() as session:
        gen_set = GenerationSet(
            id=generation_set_id,
            user_id=params.userId,
            conversation_id=params.conversationId,
            prompt=params.prompt,
            workflow_mode=params.mode
        )
        session.add(gen_set)
        session.commit()'''
content = content.replace(old_dummy, new_dummy)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated image_generate.py")
