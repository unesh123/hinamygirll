# HINAA OS — Phase 09: Asset Provenance & Retention Schema

Every creative artifact generated, edited, or encoded within HINAA OS carries an immutable metadata record adhering to the schema below.

---

## 1. Provenance Schema Specification

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "HinaaAssetProvenance",
  "type": "object",
  "required": [
    "asset_id",
    "tenant_id",
    "user_id",
    "filename",
    "media_type",
    "mime_type",
    "width",
    "height",
    "file_size_bytes",
    "sha256_hash",
    "created_at",
    "operation",
    "provider",
    "model_version"
  ],
  "properties": {
    "asset_id": {
      "type": "string",
      "pattern": "^asset-[a-f0-9]{12}$",
      "description": "Server-assigned opaque asset identifier"
    },
    "tenant_id": { "type": "string" },
    "user_id": { "type": "string" },
    "filename": { "type": "string" },
    "media_type": { "enum": ["IMAGE", "VIDEO", "ANIMATION"] },
    "mime_type": { "type": "string" },
    "width": { "type": "integer" },
    "height": { "type": "integer" },
    "file_size_bytes": { "type": "integer" },
    "sha256_hash": {
      "type": "string",
      "pattern": "^[a-f0-9]{64}$",
      "description": "Cryptographic digest of raw media bytes on disk"
    },
    "created_at": { "type": "string", "format": "date-time" },
    "operation": {
      "enum": [
        "TEXT_TO_IMAGE",
        "IMAGE_TO_IMAGE",
        "INPAINT",
        "OUTPAINT",
        "REMOVE_BACKGROUND",
        "TEXT_TO_VIDEO",
        "IMAGE_TO_VIDEO",
        "TIMELINE_EXPORT"
      ]
    },
    "provider": { "type": "string" },
    "model_version": { "type": "string" },
    "prompt": { "type": ["string", "null"] },
    "prompt_ne": { "type": ["string", "null"] },
    "seed": { "type": ["integer", "null"] },
    "parent_asset_id": { "type": ["string", "null"] },
    "mask_sha256": { "type": ["string", "null"] },
    "duration_seconds": { "type": ["number", "null"] },
    "fps": { "type": ["number", "null"] },
    "codec": { "type": ["string", "null"] },
    "is_derivative": { "type": "boolean" },
    "version_index": { "type": "integer", "minimum": 1 }
  }
}
```

---

## 2. Storage & Retention Policies

1. **Storage Path**: `apps/api/data/creative_assets/<tenant_id>/<asset_id>_<filename>`
2. **Immutability**: Stored assets are write-once. Updates create a new record pointing to `parent_asset_id` with an incremented `version_index`.
3. **Retention Policy**:
   - Intermediate masks and temporary video frames are deleted immediately upon job completion.
   - User-owned final outputs and source uploads persist indefinitely until explicit user deletion.
   - Download streams enforce `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`.
