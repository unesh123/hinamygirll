from pydantic import BaseModel, Field
from hinaa_api.tools.registry import registry, ToolDefinition

class SendEmailParams(BaseModel):
    recipient: str = Field(..., description="The email address of the recipient.")
    subject: str = Field(..., description="The subject of the email.")
    body: str = Field(..., description="The body content of the email.")

async def send_email(params: SendEmailParams) -> str:
    # Prototype stub: In a real implementation, this would use Microsoft Graph or Gmail API.
    return f"Simulated sending email to {params.recipient} with subject '{params.subject}'. (Prototype)"

send_email_def = ToolDefinition(
    name="send_email",
    display_name="Send Email",
    description="Sends an email to a specified recipient.",
    parameters={
        "recipient": {"type": "string", "description": "The email address of the recipient."},
        "subject": {"type": "string", "description": "The subject of the email."},
        "body": {"type": "string", "description": "The body content of the email."}
    },
    required_parameters=["recipient", "subject", "body"],
    voice_aliases=["send email", "email"],
    requires_confirmation=True
)

registry.register(send_email_def, send_email)
