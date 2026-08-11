class NewBiePromptBuilder:
    @staticmethod
    def build_xml_prompt(raw_prompt: str) -> str:
        return f"""
<character_1>
<appearance>
{raw_prompt}
</appearance>
</character_1>
<setting>
</setting>
<lighting>
</lighting>
"""
