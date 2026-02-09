# Keyring Guide (Trusted Signers)

Signature evidence is verified against a local keyring file containing trusted public keys.

---

## Loading Keys

PIC loads keys from (in order):

1. `PIC_KEYS_PATH` environment variable (if set)
2. `./pic_keys.json` (if present in current directory)
3. Empty keyring (no trusted signers configured)

---

## CLI Commands

### Inspect current keyring

```bash
pic-cli keys
```

### Generate starter keyring

```bash
pic-cli keys --write-example > pic_keys.json
```

### PowerShell example

```powershell
$env:PIC_KEYS_PATH=".\pic_keys.json"
pic-cli keys
```

---

## Keyring File Format

Recommended format:

```json
{
  "trusted_keys": {
    "demo_signer_v1": "u1esUbs/ZYS3PTPMIxiwsh47pyCUAv5VgzrmjEKbw6k=",
    "cfo_key_v2": {
      "public_key": "<base64-or-hex-or-PEM Ed25519 public key>",
      "expires_at": "2026-12-31T23:59:59Z"
    }
  },
  "revoked_keys": ["cfo_key_v1"]
}
```

### Key formats

Supported encodings for `public_key`:

| Format | Example | Notes |
|--------|---------|-------|
| base64 | `u1esUbs/ZYS3PTPMIxiwsh47pyCUAv5VgzrmjEKbw6k=` | Recommended |
| hex | `bb57ac51bb3f6584b73d33cc2318b0b21e3ba720...` | 64 hex chars or `0x...` prefix |
| PEM | `-----BEGIN PUBLIC KEY-----...` | Requires `cryptography` package |

### Shorthand vs expanded format

Keys can be specified in two ways:

**Shorthand** (just the key):
```json
"demo_signer_v1": "u1esUbs/ZYS3PTPMIxiwsh47pyCUAv5VgzrmjEKbw6k="
```

**Expanded** (with metadata):
```json
"cfo_key_v2": {
  "public_key": "<base64 key>",
  "expires_at": "2026-12-31T23:59:59Z"
}
```

---

## Expiry & Revocation

A signature `key_id` is treated as **inactive** if any of the following are true:

| Condition | Status |
|-----------|--------|
| Key ID not in keyring | `missing` |
| Key ID in `revoked_keys` | `revoked` |
| Key has `expires_at` and it's past | `expired` |
| Key is valid | `ok` |

Evidence verification distinguishes these cases for operator clarity.

### Example

```json
{
  "trusted_keys": {
    "active_key": "...",
    "expiring_key": {
      "public_key": "...",
      "expires_at": "2026-06-30T23:59:59Z"
    }
  },
  "revoked_keys": ["old_compromised_key"]
}
```

---

## Key Rotation Guidance

**Practical key rotation workflow:**

1. **Add new key:** Add a new key ID (e.g., `cfo_key_v2`) to the keyring
2. **Start using it:** Begin emitting proposals with `key_id="cfo_key_v2"`
3. **Revoke old key:** Add the old key ID to `revoked_keys` (or remove it entirely)
4. **Set expiry:** Optionally set `expires_at` to enforce rotation hygiene

### Example rotation

Before:
```json
{
  "trusted_keys": {
    "cfo_key_v1": "..."
  }
}
```

After rotation:
```json
{
  "trusted_keys": {
    "cfo_key_v1": "...",
    "cfo_key_v2": {
      "public_key": "...",
      "expires_at": "2027-12-31T23:59:59Z"
    }
  },
  "revoked_keys": ["cfo_key_v1"]
}
```

---

## Security Notes

### Key storage

- Keep keyring files out of version control (add to `.gitignore`)
- Use environment-specific keyrings (`PIC_KEYS_PATH`)
- Protect keyring files with appropriate filesystem permissions

### Production deployment

- Deploy keyring files via secure configuration management
- Use short-lived keys with `expires_at` for critical signers
- Monitor for `expired` and `revoked` key usage in logs

---

## See Also

- [Evidence Guide](evidence.md) — how evidence verification works
- [OpenClaw Integration](openclaw-integration.md) — keyring usage in the HTTP bridge
