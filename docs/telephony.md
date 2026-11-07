# Telephony: Hina on the phone

Hina can phone you and hold a two-way voice conversation, and you can call her number.
Built on Twilio over plain HTTPS (no SDK). Code: `apps/api/hinaa_api/telephony/`, tool `phone_call_user`.

## Call flow

1. `POST /v1/telephony/calls` (or the `phone_call_user` agent tool) asks Twilio to call you; Twilio fetches TwiML from `POST {HINAA_PUBLIC_BASE_URL}/v1/telephony/voice`.
2. `/voice` answers with `<Gather input="speech">` wrapping the opening line ("Hello boss, are you busy?"), played via `<Play>` (TTS audio) or `<Say>` when no TTS provider is configured.
3. Each thing you say posts to `/v1/telephony/gather` with `SpeechResult`. It runs through the normal chat pipeline (`stream_turn`) with a short phone-answer instruction and the call's history, then the reply is spoken and gathering resumes.
4. Every exchange is written to the call transcript and appended to your conversation memory (needs `HINAA_TELEPHONY_USER_ID`, the user id the call belongs to).
5. `/v1/telephony/status-callback` records the final call status. `GET /v1/telephony/calls` lists recent calls.

Calling Hina's Twilio number follows the same loop; only numbers on the allow-list are answered.

## Setup

1. Buy a voice-capable Twilio number; note Account SID and Auth Token.
2. In the number's Voice settings set "A call comes in" to webhook `POST https://<public-host>/v1/telephony/voice`.
3. Set env vars (in `.env.local`, never committed):

| Variable | Meaning |
| --- | --- |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Twilio credentials (token also validates webhook signatures) |
| `TWILIO_FROM_NUMBER` | Hina's Twilio number, E.164 |
| `HINAA_OWNER_PHONE_NUMBER` | Your number, E.164. Default call target |
| `HINAA_PUBLIC_BASE_URL` | Public `https://` URL Twilio can reach |
| `HINAA_TELEPHONY_ALLOWED_NUMBERS` | Extra comma-separated numbers allowed (in or out) |
| `HINAA_TELEPHONY_MAX_CALLS_PER_HOUR` | Outbound cap, default 5 |
| `HINAA_TELEPHONY_USER_ID` | User id that owns call memory |
| `HINAA_TELEPHONY_MAX_CALL_TURNS`, `HINAA_TELEPHONY_SPEECH_LANGUAGE`, `HINAA_TELEPHONY_SAY_VOICE` | Optional tuning |

`GET /v1/telephony/status` reports `configured` and which variables are missing.

## Security

- Every webhook validates `X-Twilio-Signature` (HMAC-SHA1 over public URL + sorted POST params); bad or missing signature returns 403. Only `/voice`, `/gather`, `/status-callback` and `/audio/<token>` skip user auth. Audio uses a 192-bit random token that expires in 10 minutes.
- Outbound `to` must be the owner or in the allow-list (toll-fraud guard); inbound callers must be too.
- Outbound calls are capped per hour (persisted count, survives restarts).
- `phone_call_user` is `risk_level="high"`, requires confirmation, and is blocked for non-loopback requests like other irreversible tools.
- Numbers are masked in API responses.

## Testing with a tunnel

```
cloudflared tunnel --url http://127.0.0.1:8000     # or: ngrok http 8000
export HINAA_PUBLIC_BASE_URL=https://<random>.trycloudflare.com
```

Restart the API, then `curl -X POST localhost:8000/v1/telephony/calls -H 'content-type: application/json' -d '{"reason":"testing"}'` (with your normal auth header). The public URL must match exactly what Twilio calls, since it is part of the signature.

## Costs

Twilio bills per minute for the number and each call (a few cents/min), plus Twilio speech recognition on `<Gather>`, plus your TTS and LLM usage per turn. Trial accounts can only call verified numbers.

## Next step (not implemented)

Lower latency via Media Streams (`<Connect><Stream>` websocket with streaming STT/TTS and barge-in) reusing the realtime voice path. The Gather loop is the supported path today.
